"""Estimate remaining survey area from fixed census and DR11 brick metadata."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field, load_bricks, sample_pixels
from .expansion import unit
from .fields import Census
from .run import config_path, read_csv, settings, write_csv, write_json


def executed_coverage(lon, lat, data, rollout):
    """Sample only the measured mask of each completed frozen search core."""
    searched = np.zeros(len(lon), dtype=bool)
    rows = [row for row in read_csv(rollout/'field_summary.csv') if float(row['budget']) == .3]
    for row in rows:
        folder = Path('first_batch') if row['wave']=='first' else Path(f"wide_{row['wave']}")/row['batch']
        manifest = json.loads((folder/'results/summary'/f"{row['field']}-base"/'manifest.json').read_text())
        if manifest['status']!='complete' or manifest['field']['id']!=row['field']:
            raise ValueError(f"Missing completed manifest for {row['field']}")
        inputs = manifest['inputs']
        key = {k: inputs[k] for k in ('geometry', 'mask', 'subdivision', 'census', 'root')}
        digest = hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]
        raster = np.load(data/'cache'/f"{row['field']}-{digest}"/'coverage.npy',
                         mmap_mode='r', allow_pickle=False)
        field = Field(*key['geometry'])
        x,y = field.xy(lon,lat)
        i = np.flatnonzero((abs(x)<field.width*30)&(abs(y)<field.width*30)&~searched)
        searched[i] = raster[sample_pixels(field, raster, x[i], y[i])]
    return searched, len(rows), sum(float(r['area_deg2']) for r in rows)


def run(rollout=None):
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
    prior = list(plan['previous_fields'])
    if rollout is None:
        prior.append('results/registration/fields.yaml')
    for name in prior:
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
    executed, n, native = (executed_coverage(lon,lat,data,rollout) if rollout else
                           (np.zeros(len(lon),dtype=bool),0,0.))
    rows=[]
    for survey_id,survey_name in ((3,'PS1'),(2,'DELVE'),(1,'DES')):
        for stripe,sel in (('all',np.ones(len(lon),dtype=bool)),('dec_-90_0',lat<0),
                           ('dec_0_32.375',(lat>=0)&(lat<32.375)),('dec_32.375_90',lat>=32.375)):
            area=(survey==survey_id)&sel
            rows.append(dict(survey=survey_name,declination_range=stripe,
                             eligible_proxy_deg2=float(area.sum()*cell),
                             prior_nominal_covered_proxy_deg2=float((area&previous).sum()*cell),
                             new_mask_covered_proxy_deg2=float((area&~previous&executed).sum()*cell),
                             remaining_proxy_deg2=float((area&~previous&~executed).sum()*cell)))
    out=rollout/'footprint' if rollout else Path('results/footprint')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'remaining_extent.csv',rows)
    write_json(out/'method.json',dict(job=os.environ.get('SLURM_JOB_ID'),nside=nside,pixel_area_deg2=cell,
               prior_centers=len(seen_ids),mask='DELVE census accepted plus LS south positive gr brick depth, EBV<0.10 and absolute b>=25',
               new_completed_fields=n,new_effective_native_area_deg2=native,
               scope='Brick-centre eligibility proxy. New deductions sample the executed core masks; legacy cohorts use nominal core bounds.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollout',type=Path)
    run(parser.parse_args().rollout)
