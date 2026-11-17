"""Assign fragmented residual South PS1 sky to nonoverlapping search ownership cells."""
import argparse
import json
import os
from pathlib import Path

import astropy.units as u
import numpy as np
import yaml
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
from scipy.spatial import cKDTree

from ls_satsearch.data import load_bricks, ownership, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.fields import Census
from ls_satsearch.regional_pilot import brick_covered, previous_cores
from ls_satsearch.run import settings, sha, write_csv, write_json


def run(plan, output):
    root, data, _ = settings()
    spec = yaml.safe_load(plan.read_text())
    residual = spec['residual_partition']
    history = sorted(Path('configs').glob('v1[12]/cohorts/*/fields.yaml'))
    history += [Path(f'configs/{previous}/cohorts/south_ps1/fields.yaml') for previous in ('v12g','v13')]
    cores, hashes = previous_cores(history)
    old = np.asarray(cores)
    hp = HEALPix(nside=residual['selection_nside'], order='ring')
    lon, lat = hp.healpix_to_lonlat(np.arange(hp.npix))
    ra, dec = lon.deg, lat.deg
    acceptable = regional_primary(ra,dec,'south') & Census(data).accept(ra,dec,3)
    ra,dec = ra[acceptable],dec[acceptable]
    high = abs(SkyCoord(ra,dec,unit='deg').galactic.b.deg) >= spec['min_abs_b']
    ra,dec = ra[high],dec[high]
    bricks = load_bricks(root,'south')
    tree = cKDTree(unit(bricks['RA'],bricks['DEC']))
    quality = ((bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
               & (bricks['EBV'] < spec['max_ebv'])
               & np.isfinite(bricks['PSFSIZE_G']+bricks['PSFSIZE_R']))
    good = brick_covered(ra,dec,tree,bricks,quality)
    ra,dec = ra[good],dec[good]
    area = float(hp.pixel_area.to_value(u.deg**2))
    steps = residual['tile_step_deg']
    low, high = residual['dec_min_deg'], residual['dec_max_deg']
    edges = np.linspace(low,high,round((high-low)/steps)+1)
    inside = (dec>=low)&(dec<high)
    fields, diagnostics = [], []
    for lo,hi in zip(edges[:-1],edges[1:]):
        use = (dec>=lo)&(dec<hi)
        if not use.any():
            continue
        d0 = np.rad2deg(np.arcsin((np.sin(np.deg2rad(lo))+np.sin(np.deg2rad(hi)))/2))
        dec_width = np.rad2deg(np.sin(np.deg2rad(hi))-np.sin(np.deg2rad(lo)))/np.cos(np.deg2rad(d0))
        columns = int(np.ceil(360*np.cos(np.deg2rad(d0))/steps))
        width = max(dec_width,360/columns*np.cos(np.deg2rad(d0)))+.03
        bucket = np.floor(ra[use]/(360/columns)).astype(int)
        ar,dr = ra[use],dec[use]
        for col in np.unique(bucket):
            left,right = np.array([col,col+1])*360/columns
            center = (left+right)/2
            region_here = (abs((old[:,0]-center+180)%360-180) < (right-left)/2+old[:,1])
            exclusions = old[region_here & (old[:,3]>lo) & (old[:,2]<hi)]
            policy = dict(partition=dict(ra_lo=float(left),ra_hi=float(right),dec_lo=float(lo),dec_hi=float(hi)),
                          previous_cores=exclusions.tolist(), min_abs_b=spec['min_abs_b'])
            selected = bucket==col
            n = int(ownership(ar[selected],dr[selected],policy).sum())
            proxy=n*area
            keep=proxy>=residual['minimum_proxy_deg2']
            diagnostics.append(dict(**policy['partition'],eligible_proxy_deg2=selected.sum()*area,
                                    geometrically_unsearched_proxy_deg2=proxy,registered=keep))
            if keep:
                fields.append(dict(id=f'v13r_south_ps1_{len(fields)+1:04d}',ra=float(center),dec=float(d0),width=float(width),
                                   role='pilot_eval',layer='south_ps1',region='south',survey=3,
                                   proxy_area_deg2=proxy,ownership=policy))
    output.mkdir(parents=True,exist_ok=True)
    path=output/'fields.yaml'
    path.write_text(yaml.safe_dump(dict(seed=spec['seed'],plan_sha256=sha(plan),
                                       previous_fields_sha256=hashes,fields=fields),sort_keys=False))
    (output/'search.yaml').write_bytes(Path('configs/v7/search.yaml').read_bytes())
    policy=json.loads(Path('configs/v7/production.json').read_text())
    write_json(output/'production.json',dict(policy,field_file_sha256=sha(path)))
    write_csv(output/'partition_audit.csv',diagnostics)
    write_json(output/'registration.json',dict(job=os.getenv('SLURM_JOB_ID'),fields_sha256=sha(path),
               count=len(fields),planning_nside=hp.nside,unpartitioned_proxy_deg2=(~inside).sum()*area,
               below_minimum_proxy_deg2=sum(row['geometrically_unsearched_proxy_deg2'] for row in diagnostics
                                            if not row['registered']),
               planned_proxy_deg2=sum(f['proxy_area_deg2'] for f in fields)))
    print(f'{len(fields)} residual cores, {sum(f["proxy_area_deg2"] for f in fields):.3f} proxy deg²')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
