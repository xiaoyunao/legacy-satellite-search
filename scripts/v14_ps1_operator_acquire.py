"""Acquire one real PS1 blank-skycell and image-specific reference on Slurm."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import csv
import io
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode,urljoin
from urllib.request import urlopen

from astropy.io import fits
from astropy.table import Table
import numpy as np
import yaml

from ls_satsearch.run import read_csv,sha,write_json

CONFIG=Path('configs/v14_ps1_operator/blank_pilot.yaml')
OUT=Path('results/v14/ps1_ipp/blank_pilot')


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('PS1 image acquisition/inspection requires Slurm')
    spec=yaml.safe_load(CONFIG.read_text());digest=sha(CONFIG)
    site=read_csv(Path(spec['background_table']))[spec['background_index']]
    data=Path(os.environ['LS_SAT_DATA']);folder=data/'resources/v14/ps1_operator'/digest[:16]
    folder.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    prefix=data/'software/ipp/install/lssat.lin64';executables=[]
    for name in ('psphot','psphotStack'):
        binary=prefix/'bin'/name;log=folder/(name+'-usage.txt')
        with log.open('w') as stream:
            result=subprocess.run([str(binary)],stdout=stream,stderr=subprocess.STDOUT,timeout=30)
        executables.append(dict(program=name,binary_sha256=sha(binary),usage_returncode=result.returncode,
                                usage_path=str(log),usage_sha256=sha(log)))
    url=spec['image_list_service']+'?'+urlencode(dict(ra=site['ra_deg'],dec=site['dec_deg'],
                            filters=spec['filters'],type=','.join(spec['products'])))
    with urlopen(url,timeout=90) as response:body=response.read().decode()
    listing=folder/'image_list.txt';listing.write_text(body)
    table=Table.read(body.splitlines(),format='ascii.basic',guess=False)
    cells={}
    for row in table:
        item={k:str(row[k]) for k in ('projcell','subcell','filter','type','filename','shortname')}
        cells.setdefault((int(item['projcell']),int(item['subcell'])),{})[item['filter'],item['type']]=item
    wanted={(b,t) for b in spec['filters'] for t in spec['products']}
    complete=sorted(key for key,items in cells.items() if wanted<=set(items))
    if not complete:raise ValueError('No common five-band science/weight/mask/exposure skycell; inspect native listing')
    key=complete[0];selected=[cells[key][k] for k in sorted(wanted)]
    def download(item):
        path=folder/Path(item['shortname']).name;source=urljoin(spec['image_root'],item['filename'])
        if not path.exists():
            partial=path.with_suffix(path.suffix+'.partial')
            with (folder/(path.name+'.download.log')).open('a') as stream:
                subprocess.run(['curl','--fail','--location','--retry','2','--connect-timeout','20',
                    '--max-time','900','--continue-at','-','--output',str(partial),source],
                    stdout=stream,stderr=subprocess.STDOUT,check=True)
            partial.replace(path)
        headers=[]
        with fits.open(path,lazy_load_hdus=True) as hd:
            for h in hd:
                if h.header.get('NAXIS')!=2:continue
                fields={}
                for k in ('NAXIS1','NAXIS2','BITPIX','BUNIT','BSCALE','BZERO','BOFFSET','BSOFTEN','FILTER',
                          'EXPTIME','GAIN','RDNOISE','MAGZP','MAGZERO','PSFMODEL','FWHM_MAJ','FWHM_MIN',
                          'NINPUTS','SKYCELL','TESS_ID','STACK_ID','IMAGEID','PROJCELL','SUBCELL'):
                    value=h.header.get(k)
                    if value is None or isinstance(value,(str,int,bool)):fields[k]=value
                    elif isinstance(value,(float,np.floating)):fields[k]=float(value) if np.isfinite(value) else None
                    else:fields[k]=str(value)
                headers.append(fields)
        if not headers:raise ValueError('Downloaded native product has no 2D image header')
        return dict(item,path=str(path),url=source,bytes=path.stat().st_size,sha256=sha(path),headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:products=list(pool.map(download,selected))
    write_json(OUT/'images_acquisition.json',dict(job=os.environ['SLURM_JOB_ID'],
        config_sha256=digest,code_sha256=sha(Path(__file__)),site=site,selected_cell=list(key),
        image_request=dict(url=url,path=str(listing),sha256=sha(listing)),products=products,
        executables=executables,native_processing_run=False,physical_PS1_response_validated=False,
        scope='Actual acquired native products only. Retain this checkpoint even if the separate same-cell reference query fails. No blank-source photometry or physical response is claimed.'))
    # Reuse verified column metadata, but acquire cell-specific rows including
    # secondary detections: primary-only cone photometry can belong to another cell.
    prior=Path('results/v14/repeat_full/ps1_observing_conditions/manifest.json')
    prior_meta=json.loads(prior.read_text())['metadata'];metadata=Path(prior_meta['path'])
    if sha(metadata)!=prior_meta['sha256']:raise ValueError('PS1 column metadata changed')
    names={r['name'].lower():r['name'] for r in json.loads(metadata.read_text())}
    columns=['objID','projectionID','skyCellID','primaryDetection','raStack','decStack']
    for band in spec['filters']:
        columns.extend(band+k for k in ('stackDetectID','stackImageID','PSFMag','PSFFlux','PSFFluxErr','KronMag','psfQfPerfect','expTime'))
    columns=[names[k.lower()] for k in columns]
    pages=[]
    for page in range(1,spec['reference_max_pages']+1):
        query=dict(ra=site['ra_deg'],dec=site['dec_deg'],radius=spec['reference_cone_deg'],
            projectionID=key[0],skyCellID=key[1],columns='['+','.join(columns)+']',pagesize=25000,page=page)
        source=spec['reference_api']+'?'+urlencode(query)
        with urlopen(source,timeout=120) as response:content=response.read(80000001)
        if len(content)>80000000:raise ValueError('Bounded reference page exceeded80MB')
        path=folder/f'reference_page_{page:02d}.csv';path.write_bytes(content)
        rows=list(csv.DictReader(io.StringIO(content.decode())))
        for r in rows:
            lower={k.lower():v for k,v in r.items()}
            if int(lower['projectionid'])!=key[0] or int(lower['skycellid'])!=key[1]:
                raise ValueError('Reference service did not apply selected skycell filter')
        pages.append(dict(path=str(path),url=source,rows=len(rows),bytes=len(content),sha256=sha(path)))
        if len(rows)<25000:break
    else:raise ValueError('Cell reference reached bounded paging cap')
    if not sum(p['rows'] for p in pages):raise ValueError('No same-cell reference rows; do not borrow neighboring photometry')
    write_json(OUT/'acquisition.json',dict(job=os.environ['SLURM_JOB_ID'],utc=datetime.now(timezone.utc).isoformat(),
        config_sha256=digest,code_sha256=sha(Path(__file__)),background_table_sha256=sha(Path(spec['background_table'])),
        site=site,selected_cell=list(key),complete_candidate_cells=[list(k) for k in complete],
        image_request=dict(url=url,path=str(listing),sha256=sha(listing)),products=products,
        executables=executables,reference_pages=pages,reference_metadata_sha256=sha(metadata),
        physical_PS1_response_validated=False,native_processing_run=False,scope=spec['scope']))
    print(dict(native_products=len(products),bytes=sum(p['bytes'] for p in products),
               reference_rows=sum(p['rows'] for p in pages),native_processing_run=False),flush=True)


if __name__=='__main__':run()
