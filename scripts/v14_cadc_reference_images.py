"""Qualify two independent CFHT r images before using them as morphology references."""
import argparse
import csv
import io
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np
import yaml

from ls_satsearch.matched import ps1_measurements
from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v14_cadc0706_images import crop,download
from scripts.v14_image0706 import measure_band,pixel_positions,read_image,safe_pixels

OUT=Path('results/v14/repeat_full/cadc_reference_images')
STACKS={'v14_south_response_2':'MegaPipe.628.217',
        'v14_south_response_3':'MegaPipe.433.232'}
ALTERNATE=False


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[];queries=[]
    for site,stack in STACKS.items():
        query=f"""SELECT O.observationID,P.productID,P.energy_bandpassName,
A.uri,A.productType,A.contentLength,A.contentChecksum
FROM caom2.Observation AS O JOIN caom2.Plane AS P ON O.obsID=P.obsID
JOIN caom2.Artifact AS A ON P.planeID=A.planeID
WHERE O.collection='CFHTMEGAPIPE' AND O.observationID='{stack}'
AND P.energy_bandpassName='r.MP9601'"""
        url='https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync?'+urlencode(
            dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))
        with urlopen(url,timeout=40) as response:raw=response.read(1000001)
        if len(raw)>1000000:raise ValueError('Artifact metadata exceeds bounded query')
        found=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        chosen=[dict(site=site,**r) for r in found if r['productType'] in ('science','weight')]
        if len(chosen)!=2 or {r['productType'] for r in chosen}!={'science','weight'}:
            raise ValueError('Missing or ambiguous science/weight pair: '+stack)
        rows.extend(chosen);queries.append(dict(site=site,url=url,query=query))
    write_csv(OUT/'artifacts.csv',rows)
    write_json(OUT/'registration.json',dict(queries=queries,artifact_sha256=sha(OUT/'artifacts.csv'),
        scope='Two public r stacks selected from metadata, before image quality or PS1 response is seen. Independent instrument and exposures; processing does not establish stellar truth. No physical grid/background, discovery cut or selection-function denominator is changed.'))


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Use a NERSC CPU allocation')
    data=Path(os.environ['LS_SAT_DATA']);sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    config=Path('configs/v13/matched/south');os.environ['LS_SAT_CONFIG_DIR']=str(config.resolve())
    plan=yaml.safe_load((config/'matched.yaml').read_text())
    rows=read_csv(OUT/'artifacts.csv');proof=[];results=[]
    for site in sites:
        name=site['field']
        if name not in STACKS:continue
        folder=data/'resources/v14/cadc_reference_20261119'/(name+'_alternate' if ALTERNATE else name)
        folder.mkdir(parents=True,exist_ok=True)
        files={}
        for row in rows:
            if row['site']!=name:continue
            path,entry=download(row,folder);files[row['productType']]=path;proof.append(dict(site=name,**entry))
            write_json(OUT/'downloads.json',dict(job=os.environ['SLURM_JOB_ID'],files=proof))
        center=SkyCoord(float(site['ra_deg']),float(site['dec_deg']),unit='deg')
        image,_=crop(files['science'],files['weight'],folder,'r',center.ra.deg,center.dec.deg)
        pixels,wcs,_=read_image(image)
        axis=np.linspace(-3.2,3.2,129);xx,yy=np.meshgrid(axis,axis);rr=np.hypot(xx,yy).ravel()
        grid=center.spherical_offsets_by(xx.ravel()*u.arcmin,yy.ravel()*u.arcmin)
        covered=safe_pixels(pixels,pixel_positions(wcs,grid))
        support=dict(core_full_aperture_fraction=float(covered[rr<=.75].mean()),
            stamp_full_aperture_fraction=float(covered[rr<=2.47].mean()),
            annulus_full_aperture_fraction=float(covered[(rr>=1.75)&(rr<=2.5)].mean()))
        spec=next(r for r in plan['fields'] if r['id']==site['background'])
        raw,_=ps1_measurements(spec,plan,data/'resources/ps1/tiles-v3'/site['background'])
        finite=np.isfinite(raw).all(axis=1)&(raw[:,0]>=0)&(raw[:,0]<360)&(abs(raw[:,1])<=90)
        raw=raw[finite];sky=SkyCoord(raw[:,0],raw[:,1],unit='deg');radius=sky.separation(center).arcmin
        good=((radius>1)&(radius<5)&(raw[:,2]>17)&(raw[:,2]<21.8)&(raw[:,3]>16.5)
              &(raw[:,4]>0)&(raw[:,4]<.07)&(raw[:,5]>0)&(raw[:,5]<.07)
              &(raw[:,6]>0)&(raw[:,7]>0)&(raw[:,6]-raw[:,7]<.05)
              &(raw[:,2]-raw[:,3]>0)&(raw[:,2]-raw[:,3]<1.25))
        try:
            measured=measure_band(image,sky[good],raw[good,3],center,487253)
            results.append(dict(site=name,state='measured',support=support,**measured['report']))
        except ValueError as error:
            results.append(dict(site=name,state='unusable',support=support,reason=str(error),path=image.name))
        write_json(OUT/'summary.json',dict(job=os.environ['SLURM_JOB_ID'],measurements=results,
            artifact_sha256=sha(OUT/'artifacts.csv'),code_sha256=sha(Path(__file__)),
            scope='Actual WCS/positive-weight full-aperture support and PS1-r-equivalent aperture noise only. Core radius 0.75 arcmin; background 1.75–2.5 arcmin. These measurements do not yet validate faint blue-star morphology, calibration transfer or truth-level PS1 response.'))
        print(name,results[-1],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run'))
    p.add_argument('--alternate',action='store_true');a=p.parse_args()
    if a.alternate:
        ALTERNATE=True;OUT=OUT/'alternates'
        STACKS={'v14_south_response_2':'MegaPipe.630.216','v14_south_response_3':'MegaPipe.434.232'}
    prepare() if a.mode=='prepare' else run()
