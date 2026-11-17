"""Inject single PSFs into real DR11 g/r coadd stamps and recover blind local maxima."""

import argparse
import os
from pathlib import Path

import fitsio
import numpy as np
from astropy.stats import mad_std, sigma_clipped_stats
from scipy.ndimage import correlate, maximum_filter

from ls_satsearch.data import load_bricks
from ls_satsearch.expansion import unit
from ls_satsearch.run import config_path, settings, sha, write_csv, write_json
import yaml


def image_planes(prefix, band, size):
    with fitsio.FITS(f'{prefix}-image-{band}.fits.fz') as fits:
        height, width = fits[1].get_dims()
        y, x = height // 2, width // 2
        stamp = (slice(y-size, y+size), slice(x-size, x+size))
        image = fits[1][stamp]
    with fitsio.FITS(f'{prefix}-invvar-{band}.fits.fz') as fits:
        weight = fits[1][stamp]
    return stamp, image.astype(float), weight.astype(float)


def psf(sigma, dx=0., dy=0.):
    radius = int(np.ceil(4*sigma))+1
    axis = np.arange(-radius, radius+1)
    y, x = np.meshgrid(axis, axis, indexing='ij')
    kernel = np.exp(-.5*((x-dx)**2+(y-dy)**2)/sigma**2)
    return kernel/kernel.sum()


def detect(score, x, y, match_radius, threshold):
    yy, xx = np.indices(score.shape)
    maxima = score == maximum_filter(score, size=3, mode='constant', cval=-np.inf)
    matched = maxima & (np.hypot(xx-x, yy-y) <= match_radius)
    return bool(np.any(matched & (score >= threshold)))


def trial(image, weight, valid, seeing, rng, magnitudes, trials):
    sigma = seeing / .262 / np.sqrt(8*np.log(2))
    kernel = psf(sigma)
    radius = kernel.shape[0]//2
    _, sky, _ = sigma_clipped_stats(image[valid])
    denom = np.sqrt(np.maximum(correlate(weight, kernel**2), 1e-20))
    blank = correlate((image-sky)*weight, kernel)/denom
    # Correct formal curvature errors for coadd pixel covariance with the
    # central, robust width of the measured blank score distribution.
    correction = mad_std(blank[valid], ignore_nan=True)
    if not np.isfinite(correction) or correction <= 0:
        raise ValueError('Invalid empirical coadd noise')
    blank /= correction
    parents = (blank == maximum_filter(blank, size=3)) & (blank >= 5) & valid
    from scipy.ndimage import distance_transform_edt
    neighbor_dist = distance_transform_edt(~parents)
    offsets = np.argwhere(valid & (correlate(valid.astype(float), np.ones(kernel.shape)) == kernel.size))
    offsets = offsets[(offsets >= 2*radius+3).all(axis=1)
                      & (offsets < np.array(image.shape)-2*radius-3).all(axis=1)]
    if len(offsets) < trials:
        raise ValueError('Too few valid source-injection sites')
    # Compare typical sky and deliberately near-neighbour positions separately.
    samples = {'uniform': offsets, 'near_peak': offsets[
        (neighbor_dist[tuple(offsets.T)] >= .5 * seeing/.262)
        & (neighbor_dist[tuple(offsets.T)] <= 1.5 * seeing/.262)]}
    for label, sites in samples.items():
        if not len(sites):
            continue
        sample = sites[rng.choice(len(sites), min(trials, len(sites)), replace=False)]
        for mag0, transmission in magnitudes:
            flux = 10**(.4*(22.5-mag0))*transmission
            n_recovered, n_blank, both, n_phot = 0, 0, 0, 0
            measured = []
            for y,x in sample:
                dx,dy = rng.uniform(-.5,.5,2)
                half = 2*radius+3
                ys,xs = slice(y-half,y+half+1),slice(x-half,x+half+1)
                # Convolution of a single injected source with the exact same
                # weighted filter as used on the observed image.
                perturb = np.zeros((2*half+1,2*half+1))
                src = slice(half-radius,half+radius+1)
                perturb[src,src] = flux*psf(sigma,dx,dy)
                excess = correlate(perturb*weight[ys,xs],kernel)/denom[ys,xs]/correction
                before = blank[ys,xs]
                reach = .65*seeing/.262
                pre = detect(before,half+dx,half+dy,reach,5)
                post = detect(before+excess,half+dx,half+dy,reach,5)
                recovered_flux = (before+excess)[half,half]/denom[y,x]*correction
                n_recovered += post
                n_blank += pre
                both += post and pre
                n_phot += recovered_flux > 0
                if recovered_flux > 0:
                    measured.append(-2.5*np.log10(recovered_flux/flux))
            yield dict(site=label, mag0=mag0, n=len(sample), recovered=n_recovered, blank=n_blank,
                       overlap=both, new_peak=n_recovered-both, positive_photometry=n_phot,
                       mag_error_median=np.median(measured) if measured else None,
                       noise_correction=correction)


def run(output):
    root, _, cfg = settings()
    region = cfg['region']
    spec = yaml.safe_load(config_path('matched.yaml').read_text())
    bricks = load_bricks(root,region)
    eligible = (bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)
    good = bricks[eligible]
    rows, inputs = [], []
    rng = np.random.default_rng(483318)
    for field in [f for f in spec['fields'] if f['role']=='pilot_dev'][:3]:
        center = unit(field['ra'],field['dec'])
        index = np.argmin(np.linalg.norm(unit(good['RA'],good['DEC'])-center,axis=1))
        brick = good[index]
        name = brick['BRICKNAME'].strip()
        prefix = root/region/'coadd'/name[:3]/name/f'legacysurvey-{name}'
        for band, coeff in (('g',3.214),('r',2.165)):
            stamp, image, weight = image_planes(prefix,band,384)
            with fitsio.FITS(f'{prefix}-maskbits.fits.fz') as fits:
                mask = fits[1][stamp]
            trans = 10**(-.4*coeff*float(brick['EBV']))
            seeing = float(brick[f'PSFSIZE_{band.upper()}'])
            valid = (weight>0)&np.isfinite(image)&((mask&sum(1<<b for b in cfg['reject_maskbits']+[0]))==0)
            weight = np.where(valid,weight,0)
            image = np.where(valid,image,0)
            values = [(g,trans) for g in (21.5,22.5,23.,23.5,24.,24.5,25.)]
            for row in trial(image,weight,valid,seeing,rng,values,128):
                rows.append(dict(region=region,field=field['id'],brick=name,band=band,
                                 seeing_arcsec=seeing, ebv=float(brick['EBV']),**row))
            inputs.extend(str(f'{prefix}-{product}.fits.fz') for product in
                          (f'image-{band}',f'invvar-{band}'))
        inputs.append(str(f'{prefix}-maskbits.fits.fz'))
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/f'{region}.csv',rows)
    write_json(output/f'{region}.json',dict(inputs=inputs,job=os.getenv('SLURM_JOB_ID'),
               config_sha256=sha(config_path('matched.yaml')),seed=483318,
               scope='Independent g/r coadd detection at 5 blank-corrected sigma with Gaussian PSFs. '
               'Local maxima are proxies for source extraction. Tractor joint detection, deblending and TYPE are not replayed.'))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    run(p.parse_args().output)
