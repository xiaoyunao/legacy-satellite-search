"""Measure external-reference coverage from real PS1 exposure and mask images."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS
import numpy as np
import yaml

from ls_satsearch.data import load_bricks
from ls_satsearch.run import settings,field_cache,sha,write_json

CONFIG=Path('configs/v14_cosmos_reference/native_coverage.yaml')
OUT=Path('results/v14/repeat_full/cosmos_reference/native_image_coverage')


def image_pixels(path):
    with fits.open(path,memmap=False) as hd:
        hdu=next(h for h in hd if h.data is not None and h.data.ndim==2)
        header=hdu.header.copy()
        # Full PS1 skycells omit RADESYS; fix only the in-memory WCS header.
        if 'RADESYS' not in header:header['RADESYS']='FK5'
        return hdu.data.copy(),WCS(header)


def sample(image,wcs,ra,dec):
    x,y=wcs.all_world2pix(ra,dec,0)
    finite=np.isfinite(x)&np.isfinite(y)
    ix=np.floor(np.where(finite,x,0)+.5).astype(int);iy=np.floor(np.where(finite,y,0)+.5).astype(int)
    inside=finite&(ix>=0)&(iy>=0)&(ix<image.shape[1])&(iy<image.shape[0])
    values=np.zeros(ra.shape,dtype=image.dtype);values[inside]=image[iy[inside],ix[inside]]
    return inside,values


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Real image processing requires Slurm')
    spec=yaml.safe_load(CONFIG.read_text());config_hash=sha(CONFIG)
    os.environ['LS_SAT_CONFIG_DIR']='configs/v14_cosmos_reference'
    root,data,cfg=settings();m=yaml.safe_load(Path('configs/v14_cosmos_reference/matched.yaml').read_text())
    field_spec=dict(m['fields'][0],width=m['width_deg'],buffer_arcmin=0)
    field,_,ls_area,ls_inputs=field_cache(root,data,field_spec,cfg,load_bricks(root,'south'))
    folder=data/'resources/independent/cosmos2020/PS1_native';folder.mkdir(parents=True,exist_ok=True)
    requests=[];rows={}
    for ra,dec in spec['requested_positions']:
        url=spec['image_list_service']+'?'+urlencode(dict(ra=ra,dec=dec,filters=spec['filters'],type=','.join(spec['products'])))
        with urlopen(url,timeout=90) as response:body=response.read().decode()
        listing=folder/f'list-{ra}-{dec}.txt';listing.write_text(body)
        requests.append(dict(url=url,path=str(listing),sha256=sha(listing)))
        table=Table.read(body.splitlines(),format='ascii.basic',guess=False)
        for row in table:
            if str(row['type']) not in spec['products']:continue
            item={key:str(row[key]) for key in ('projcell','subcell','filter','type','filename','shortname')}
            rows[item['filename']]=item
    if not rows:raise ValueError('No actual PS1 exposure/mask images returned')
    def download(item):
        path=folder/item['shortname'];url=spec['image_root']+item['filename']
        if not path.exists():
            partial=path.with_suffix(path.suffix+'.partial')
            subprocess.run(['curl','--fail','--location','--retry','2','--connect-timeout','20','--max-time','900','--continue-at','-','--output',str(partial),url],check=True)
            partial.replace(path)
        with fits.open(path,lazy_load_hdus=True) as hd:
            if not any(h.header.get('NAXIS')==2 for h in hd):raise ValueError('Image product lacks 2D image')
        return dict(item,path=str(path),url=url,bytes=path.stat().st_size,sha256=sha(path))
    with ThreadPoolExecutor(max_workers=2) as pool:products=list(pool.map(download,rows.values()))
    grouped={}
    for item in products:grouped.setdefault((item['projcell'],item['subcell'],item['filter']),{})[item['type']]=item
    cell=field.step/cfg['coverage_subdivision'];axis=(np.arange(len(ls_area))+.5)*cell-field.limit
    row,col=np.nonzero(ls_area);ra,dec=field.sky(axis[col],axis[row])
    band_valid={band:np.zeros(len(row),bool) for band in spec['filters']};fatal=sum(spec['rejected_pixel_flags']);tile_counts=[]
    for (proj,sub,band),items in grouped.items():
        if set(items)!=set(spec['products']):raise ValueError('Unpaired exposure/mask product')
        exposure,ewcs=image_pixels(items['stack.exp']['path']);mask,mwcs=image_pixels(items['stack.mask']['path'])
        ei,ev=sample(exposure,ewcs,ra,dec);mi,mv=sample(mask,mwcs,ra,dec)
        good=ei&mi&np.isfinite(ev)&(ev>0)&((mv.astype(np.int64)&fatal)==0)
        band_valid[band]|=good;tile_counts.append(dict(projcell=proj,subcell=sub,band=band,valid_LS_cells=int(good.sum()),shape=list(exposure.shape)))
    common=np.logical_and.reduce(list(band_valid.values()));coverage=np.zeros_like(ls_area);coverage[row[common],col[common]]=True
    pending=folder/('coverage-'+os.environ['SLURM_JOB_ID']+'.npy');np.save(pending,coverage,allow_pickle=False)
    digest=sha(pending);target=folder/('coverage-'+digest+'.npy')
    if target.exists():
        if sha(target)!=digest:raise ValueError('Immutable coverage artifact changed')
        pending.unlink()
    else:pending.replace(target)
    if sha(CONFIG)!=config_hash:raise ValueError('Native coverage policy changed during measurement')
    OUT.mkdir(parents=True,exist_ok=True)
    write_json(OUT/'manifest.json',dict(job=os.environ['SLURM_JOB_ID'],utc=datetime.now(timezone.utc).isoformat(),config_sha256=config_hash,code_sha256=sha(Path(__file__)),image_requests=requests,products=products,tiles=tile_counts,LS_inputs=ls_inputs,LS_valid_cells=int(ls_area.sum()),PS1_band_valid_LS_cells={k:int(v.sum()) for k,v in band_valid.items()},common_valid_cells=int(common.sum()),pixel_area_deg2=(cell/60)**2,common_control_deg2=float(common.sum()*(cell/60)**2),coverage=dict(path=str(target),sha256=digest,shape=list(coverage.shape)),scope=spec['scope']+' Native central-pixel coverage is not PSF-weighted completeness or census footprint membership. PS1 public DR1/DR2 products are 3pi, not Medium Deep stacks.'))
    print('NATIVE_REFERENCE_COVERAGE',len(products),int(common.sum()),flush=True)


if __name__=='__main__':run()
