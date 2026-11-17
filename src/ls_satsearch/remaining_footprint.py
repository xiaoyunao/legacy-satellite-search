"""Estimate remaining survey area from fixed census and DR11 brick metadata."""

import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field, load_bricks
from .expansion import unit
from .fields import Census
from .run import config_path, settings, write_csv, write_json


def run():
    root,data,_=settings()
    plan=yaml.safe_load(config_path('expansion.yaml').read_text())
    nside=256
    grid=HEALPix(nside=nside,order='ring')
    lon,lat=grid.healpix_to_lonlat(np.arange(grid.npix))
    lon,lat=lon.to_value(u.deg),lat.to_value(u.deg)
    sky=SkyCoord(lon,lat,unit='deg')
    high=np.abs(sky.galactic.b.deg)>=25.
    lon,lat=lon[high],lat[high]
    atlas=Census(data)
    survey=np.zeros(len(lon),dtype=int)
    for k in (1,2,3):
        survey[atlas.accept(lon,lat,k)]=k
    keep=survey>0
    lon,lat,survey=lon[keep],lat[keep],survey[keep]
    bricks=load_bricks(root)
    distance,index=cKDTree(unit(bricks['RA'],bricks['DEC'])).query(unit(lon,lat),k=1)
    # PSFDEPTH in the survey-bricks summary is already in magnitudes.
    good=(distance<np.radians(.23))&(bricks['PSFDEPTH_G'][index]>0)&(bricks['PSFDEPTH_R'][index]>0)
    good&=(bricks['EBV'][index]<.10)&np.isfinite(bricks['PSFSIZE_G'][index]+bricks['PSFSIZE_R'][index])
    lon,lat,survey=lon[good],lat[good],survey[good]
    previous=np.zeros(len(lon),dtype=bool)
    seen_ids=set()
    for name in [*plan['previous_fields'],'results/registration/fields.yaml']:
        fields=yaml.safe_load(Path(name).read_text())['fields']
        for spec in fields:
            ident=(spec['id'],spec['ra'],spec['dec'])
            if ident in seen_ids:
                continue
            seen_ids.add(ident)
            if spec.get('role') not in ('pilot_eval','pilot_dev','deep_control'):
                continue
            field=Field(spec['ra'],spec['dec'],spec['width'],1/6,buffer=0)
            x,y=field.xy(lon,lat)
            inside=(abs(x)<field.width*30)&(abs(y)<field.width*30)
            previous|=inside
    cell=grid.pixel_area.to_value(u.deg**2)
    rows=[]
    for survey_id,survey_name in ((3,'PS1'),(2,'DELVE'),(1,'DES')):
        for stripe,sel in (('all',np.ones(len(lon),dtype=bool)),('dec_-90_0',lat<0),
                           ('dec_0_32.375',(lat>=0)&(lat<32.375)),('dec_32.375_90',lat>=32.375)):
            area=(survey==survey_id)&sel
            rows.append(dict(survey=survey_name,declination_range=stripe,
                             eligible_proxy_deg2=float(area.sum()*cell),
                             prior_nominal_covered_proxy_deg2=float((area&previous).sum()*cell),
                             remaining_proxy_deg2=float((area&~previous).sum()*cell)))
    out=Path('results/footprint')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'remaining_extent.csv',rows)
    write_json(out/'method.json',dict(job=os.environ.get('SLURM_JOB_ID'),nside=nside,pixel_area_deg2=cell,
               prior_centers=len(seen_ids),mask='DELVE census accepted plus LS south positive gr brick depth, EBV<0.10 and absolute b>=25',
               scope='Brick-centre proxy from sampled input pixels. Edge coverage is measured only by executed scans.'))


if __name__=='__main__':
    run()
