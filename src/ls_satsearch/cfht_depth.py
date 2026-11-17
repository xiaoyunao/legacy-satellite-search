"""Measure the r-band follow-up depth with calibrated cutouts and off-core stars."""

import argparse
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np
from scipy.ndimage import minimum_filter
from scipy.spatial import cKDTree
import yaml

from .hsc_depth_audit import aperture, candidate_sources, robust_sigma
from .image_cmd import ps1_refs, red_stack, stack_zero_point
from .matched import reddening
from .run import sha, write_json


def run(config, data, output):
    plan = yaml.safe_load(config.read_text())
    target_path = Path(plan['target'])
    target = yaml.safe_load(target_path.read_text())
    center = SkyCoord(target['ra_deg'], target['dec_deg'], unit='deg')
    ref_path = data/'resources'/target['scratch_revision']/target['candidate']/'ps1.csv'
    folder = data/'resources/v10/survey63/cfht'
    pixel = plan['stack_pixel_arcsec']
    aperture_arcsec = plan['r_aperture_arcsec']
    inner, outer = plan['annulus_arcmin']
    half = int(np.ceil((outer * 60 + 5) / pixel))
    axis = np.arange(-half, half + 1) * pixel
    x, y = np.meshgrid(axis, axis)
    radius = np.hypot(x, y) / 60
    core = radius <= target['center_aperture_arcmin']
    ring = (radius >= inner) & (radius <= outer)
    sky = center.spherical_offsets_by(x.ravel()*u.arcsec, y.ravel()*u.arcsec)
    ref, mag = ps1_refs(ref_path, center, *plan['reference_arcmin'])
    image, count, records = red_stack(folder, ref, mag, sky, len(axis), pixel,
                                      aperture_arcsec, visits=plan['cfht_visits'])
    rule = dict(plan, aperture_arcsec=aperture_arcsec)
    peaks = candidate_sources(image, threshold=7)
    scale, validation = stack_zero_point(image, 'r', rule, ref_path, center, pixel, peaks)
    image *= scale
    # Require all photometry pixels and the local sky ring to have two visits.
    covered = minimum_filter(count, size=31, mode='constant', cval=0) >= 2
    image[count < 2] = np.nan
    detected = cKDTree(peaks)
    rng = np.random.default_rng(plan['seed'])
    ebv = float(reddening([center.ra.deg], [center.dec.deg])[0])
    regions = {}
    for name, mask in [('core', core), ('control_annulus', ring)]:
        choices = np.flatnonzero(mask & covered)
        ij = np.column_stack(np.unravel_index(
            rng.choice(choices, min(4500, len(choices)), replace=False), image.shape))[:, ::-1]
        ij = ij[detected.query(ij)[0] * pixel > 2.5]
        blank = np.array([aperture(image, pos, aperture_arcsec / pixel)[0] for pos in ij])
        blank = blank[np.isfinite(blank)]
        if len(blank) < 100:
            raise ValueError(f'Insufficient {name} blank apertures')
        good = abs(blank - np.median(blank)) < 3 * robust_sigma(blank)
        noise = robust_sigma(blank[good])
        limit = 25 - 2.5 * np.log10(5 * noise)
        regions[name] = dict(two_visit_full_aperture_fraction=float(covered[mask].mean()),
                             blank_apertures=int(good.sum()), r5_ps1_equiv=float(limit),
                             r0_5_ps1_equiv=float(limit - 2.271 * ebv))
    east, north = center.spherical_offsets_to(ref)
    xy = np.column_stack((east.arcsec, north.arcsec)) / pixel + half
    distance, match = detected.query(xy)
    cross = peaks[match[distance * pixel < .8]]
    small = np.array([aperture(image, pos, .60 / pixel)[0] for pos in cross])
    large = np.array([aperture(image, pos, 1.45 / pixel)[0] for pos in cross])
    good = np.isfinite(small) & np.isfinite(large) & (small > 0) & (large > 0)
    concentration = -2.5 * np.log10(small[good] / large[good])
    write_json(output, dict(job=os.environ.get('SLURM_JOB_ID'), candidate=target['candidate'],
               config_sha256=sha(config), target_config_sha256=sha(target_path),
               reference_sha256=sha(ref_path), ebv=ebv, center_usable=bool(covered[half, half]),
               visits=records, calibration=validation, regions=regions,
               bright_ps1_point_proxy=dict(n=int(good.sum()),
                   concentration_median_mag=float(np.median(concentration)),
                   concentration_robust_sigma_mag=float(robust_sigma(concentration))),
               scope='Finite calibrated CFHT science pixels. No separate CADC DQ/weight planes used. '
                     'Depth is local aperture noise on a PS1 r scale. Bright-star morphology is '
                     'a repeatability diagnostic; faint completeness and classification remain unmeasured.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.config, Path(os.environ['LS_SAT_DATA']), args.output)
