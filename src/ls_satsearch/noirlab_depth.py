"""Calibrate the partly covering independent DECam g exposure with PS1 stars."""

import argparse
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
import numpy as np
from scipy.ndimage import minimum_filter
import yaml

from .hsc_depth_audit import aperture, references, robust_sigma
from .matched import reddening
from .noirlab_probe import clipped_coverage
from .run import sha, write_json


def plane(path):
    with fits.open(path,memmap=False) as hdus:
        h=next(h for h in hdus if h.data is not None and h.data.ndim==2)
        return h.data.copy(),h.header


def run(config, folder, output, expnum=562858, ccd_ids=(31,32)):
    target=yaml.safe_load(config.read_text())
    data=Path(os.environ['LS_SAT_DATA'])
    ps1=data/'resources'/target['scratch_revision']/target['candidate']/'ps1.csv'
    centre=SkyCoord(target['ra_deg'],target['dec_deg'],unit='deg')
    reference,magnitude=references(ps1,centre)
    rh=target['rh_arcmin']
    axis=np.arange(-6*rh,6*rh+.025,.05)
    x,y=np.meshgrid(axis,axis)
    radius=np.hypot(x,y)
    core=radius<=1.5*rh
    off=(radius>=3.5*rh)&(radius<=6*rh)
    coords=centre.spherical_offsets_by(x*u.arcmin,y*u.arcmin)
    random=np.random.default_rng(486194)
    trial=random.choice(np.flatnonzero(off),size=1500,replace=False)
    joint=np.zeros_like(core)
    chip_reports=[]
    for cid in ccd_ids:
        files={k:folder/f'{k}-{cid}.fits' for k in ('image','weight','dq')}
        image,h=plane(files['image'])
        weight,w=plane(files['weight'])
        dq,q=plane(files['dq'])
        if image.shape!=weight.shape or image.shape!=dq.shape or not h['DETPOS']==w['DETPOS']==q['DETPOS']:
            raise ValueError(f'Incompatible FITS archive CCD products for extension {cid}')
        good=np.isfinite(image)&np.isfinite(weight)&(weight>0)&(dq==0)
        img=np.where(good,image,np.nan)
        wcs=WCS(h).celestial
        usable=minimum_filter(good,size=9,mode='constant',cval=False)
        for on_axis in (usable,usable.T):
            on_axis[:15]=False
            on_axis[-15:]=False
        coverage=clipped_coverage(wcs,np.where(usable,0.,np.nan),coords)
        joint|=coverage
        xy=np.column_stack(wcs.world_to_pixel(reference))
        f=np.array([aperture(img,p,radius=4)[0] for p in xy])
        take=np.isfinite(f)&(f>0)
        refs=np.argsort(reference.ra.deg[take])
        offsets=magnitude[take]+2.5*np.log10(f[take])
        hold=np.zeros(len(offsets),dtype=bool)
        hold[refs[::3]]=True
        training=offsets[~hold]
        if len(training)<6 or hold.sum()<3:
            chip_reports.append(dict(ccd=h['DETPOS'],status='insufficient PS1 calibrators',
                                     calibrators=int(take.sum()),core_fraction=float(coverage[core].mean())))
            continue
        start=np.median(training)
        keep=abs(training-start)<max(.10,3*robust_sigma(training))
        zero=float(np.median(training[keep]))
        residual=offsets[hold]-zero
        pos=np.column_stack(wcs.world_to_pixel(coords.ravel()[trial]))
        blank=np.array([aperture(img,p,radius=4)[0] for p in pos])
        blank=blank[np.isfinite(blank)]
        if len(blank)<100:
            raise ValueError(f'Insufficient blank apertures on {h["DETPOS"]}')
        noise=robust_sigma(blank)
        good_blank=abs(blank-np.median(blank))<3*noise
        limit=float(zero-2.5*np.log10(5*robust_sigma(blank[good_blank])))
        ebv=float(reddening(np.array([centre.ra.deg]),np.array([centre.dec.deg]))[0])
        chip_reports.append(dict(ccd=h['DETPOS'],status='calibrated',calibrators=int(keep.sum()),
          holdout=int(hold.sum()),holdout_median_mag=float(np.median(residual)),
          holdout_sigma_mag=float(robust_sigma(residual)),zeropoint_ps1_g=zero,blank_apertures=int(good_blank.sum()),
          g5_ps1_equiv=limit,g0_5_ps1_equiv=limit-3.172*ebv,core_fraction=float(coverage[core].mean()),
          file_sha256={k:sha(p) for k,p in files.items()}))
    index=np.unravel_index(coords.separation(centre).argmin(),coords.shape)
    write_json(output,dict(job=os.environ.get('SLURM_JOB_ID'),expnum=expnum,aperture_radius_pixels=4,
               core_usable_fraction=float(joint[core].mean()),annulus_usable_fraction=float(joint[off].mean()),
               center_usable=bool(joint[index]),measurements=chip_reports,
               scope='Positive weight and zero DQ, complete aperture and numerically valid margins. '
                     'Empirical PS1 g calibration and local blank-aperture noise. Completeness remains unmeasured.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config',type=Path)
    p.add_argument('folder',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--expnum',type=int,default=562858)
    p.add_argument('--ccd-ids',nargs='+',type=int,default=(31,32))
    a=p.parse_args()
    run(**vars(a))
