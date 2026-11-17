"""Measure where the geometric primary rule may leave singly imaged DR11 sky unassigned."""
import os
from pathlib import Path

import astropy.units as u
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import load_bricks, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.regional_pilot import brick_covered
from ls_satsearch.run import write_csv, write_json


def main():
    root = Path(os.environ['LS_DR11_ROOT'])
    grid = HEALPix(nside=512, order='ring')
    lon, lat = grid.healpix_to_lonlat(np.arange(grid.npix))
    ra,dec = lon.deg,lat.deg
    cell = grid.pixel_area.to_value(u.deg**2)
    native = {}
    for region in ('north','south'):
        bricks=load_bricks(root,region)
        tree=cKDTree(unit(bricks['RA'],bricks['DEC']))
        usable=(bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)
        native[region]=brick_covered(ra,dec,tree,bricks,usable)
    rows=[]
    for region,other in (('north','south'),('south','north')):
        primary=regional_primary(ra,dec,region)
        separated=native[region]&~primary&~native[other]
        rows.append(dict(region=region,native_gr_brick_proxy_deg2=native[region].sum()*cell,
                         geometrically_assigned_deg2=(native[region]&primary).sum()*cell,
                         outside_primary_with_no_other_gr_deg2=separated.sum()*cell,
                         raw_two_native_overlap_deg2=(native[region]&native[other]).sum()*cell))
        data=Path(os.environ['LS_SAT_DATA'])/'runs/v14'
        np.savez_compressed(data/f'{region}_outside_primary.npz',ra=ra[separated],dec=dec[separated])
    out=Path('results/v14/footprint')
    write_csv(out/'native_ownership_audit.csv',rows)
    write_json(out/'native_ownership_audit.json',dict(job=os.getenv('SLURM_JOB_ID'),nside=grid.nside,
               note='The footprint proxy uses bounded gr brick magnitude and exact native assignment. '
                    'It identifies planning gaps; shared or single usable WCS pixels require exposure and bad-pixel masks.'))


if __name__=='__main__':
    main()
