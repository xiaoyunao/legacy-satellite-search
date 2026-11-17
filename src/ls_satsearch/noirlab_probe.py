"""Measure archived CCD coverage at a frozen candidate and its control annulus."""

import argparse
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
import numpy as np
import yaml

from .run import sha, write_csv, write_json


def clipped_coverage(wcs, data, coords):
    x,y=wcs.world_to_pixel(coords)
    inside=(x>=1)&(x<data.shape[1]-2)&(y>=1)&(y<data.shape[0]-2)
    ok=np.zeros(coords.shape,dtype=bool)
    ok[inside]=np.isfinite(data[np.rint(y[inside]).astype(int),np.rint(x[inside]).astype(int)])
    return ok


def run(config,output,paths):
    target=yaml.safe_load(config.read_text())
    centre=SkyCoord(target['ra_deg'],target['dec_deg'],unit='deg')
    rh=target['rh_arcmin']
    axis=np.arange(-6*rh,6*rh+.025,.05)
    east,north=np.meshgrid(axis,axis)
    separations=np.hypot(east,north)
    in_core=separations<=1.5*rh
    in_annulus=(separations>=3.5*rh)&(separations<=6*rh)
    coords=centre.spherical_offsets_by(east*u.arcmin,north*u.arcmin)
    joint=np.zeros(coords.shape,dtype=bool)
    records=[]
    for p in paths:
        with fits.open(p,memmap=False) as images:
            for h in images:
                if h.data is None or h.data.ndim!=2:
                    continue
                wcs=WCS(h.header).celestial
                if not wcs.has_celestial:
                    continue
                covered=clipped_coverage(wcs,h.data,coords)
                joint|=covered
                x,y=wcs.world_to_pixel(centre)
                records.append(dict(file=p.name,sha256=sha(p),expnum=images[0].header.get('EXPNUM'),
                    date_obs=images[0].header.get('DATE-OBS'),filter=images[0].header.get('FILTER'),
                    exptime=images[0].header.get('EXPTIME'),ccd=h.header.get('DETPOS'),
                    x_at_center=float(x),y_at_center=float(y),nx=h.data.shape[1],ny=h.data.shape[0],
                    core_geometric=float(covered[in_core].mean()),annulus_geometric=float(covered[in_annulus].mean())))
    if not records:
        raise ValueError('Expected calibrated two-dimensional FITS cutouts with celestial WCS')
    output.mkdir(exist_ok=True,parents=True)
    write_csv(output/'noirlab_ccd_coverage.csv',records)
    write_json(output/'noirlab_ccd_coverage.json',dict(job=os.environ.get('SLURM_JOB_ID'),
               core_union=float(joint[in_core].mean()),annulus_union=float(joint[in_annulus].mean()),
               central_pixel_coverage=bool(clipped_centre(coords,centre,joint)),
               scope='Finite image pixels in archive WCS; quality, depth and PSF need validation if usable.'))


def clipped_centre(coords, centre, mask):
    j=np.unravel_index(coords.separation(centre).argmin(),coords.shape)
    return mask[j]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('paths',type=Path,nargs='+')
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.plan,a.output,a.paths)
