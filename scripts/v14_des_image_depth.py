"""Compare DES Y6 and LS formal 2-arcsec aperture image depth on common sky."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from astropy import units as u
from astropy_healpix import HEALPix
from astropy.wcs import WCS
import fitsio
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import load_bricks
from ls_satsearch.expansion import unit
from ls_satsearch.run import sha, write_csv, write_json
from scripts.v14_qualified_aitoff import axes_map, save

NATIVE_DES_NSIDE = 1024
MAP_NSIDE = 256
SAMPLE_NSIDE = 16
RADIUS_ARCSEC = 1.
FRACTION_GRID = (np.arange(16) + .5) / 16 - .5
DES_URL = 'https://desdr-server.ncsa.illinois.edu/despublic/y6a2_files/y6_sp_maps/main_sp_maps/'
DES_DIGEST = {
    'g': 'e8c6a6ba93f18768ea44b1d0a41da61556a18da505a54b18cdff6bba38230c73',
    'r': '6cb6c02c67d8a25a30c5465ab6b85d2d5d0e13ef5deffbd4fd28b263f705fc57',
}


def des_values(path, band):
    if sha(path) != DES_DIGEST[band]:
        raise ValueError('Released DES map bytes differ from the acquired reference')
    with fitsio.FITS(path) as f:
        hdr = f[1].read_header()
        if (int(hdr.get('NSIDE', NATIVE_DES_NSIDE)) != NATIVE_DES_NSIDE
                or str(hdr.get('ORDERING', 'RING')).strip() != 'RING'):
            raise ValueError('Unexpected DES map resolution or ordering')
        table = f[1].read(columns=['PIXEL', 'SIGNAL', 'FRACDET'])
    pix = table['PIXEL']
    values = np.full(12*NATIVE_DES_NSIDE**2, np.nan)
    if pix.min() < 0 or pix.max() >= len(values) or np.unique(pix).size != len(pix):
        raise ValueError('Invalid sparse DES pixel index')
    use = (table['FRACDET'] >= .8) & (table['SIGNAL'] > 18.) & (table['SIGNAL'] < 30.)
    values[pix[use]] = table['SIGNAL'][use]
    return values


def sample_sky(raster, official):
    sky = HEALPix(nside=MAP_NSIDE, order='ring', frame='galactic')
    coarse = HEALPix(nside=SAMPLE_NSIDE, order='ring', frame='galactic')
    des_grid = HEALPix(nside=NATIVE_DES_NSIDE, order='ring', frame='icrs')
    information = np.load(raster)
    available = np.flatnonzero((information['bits'] == 2) & (information['regions'] == 1))
    fine = sky.healpix_to_skycoord(available)
    observed = np.column_stack([m[des_grid.skycoord_to_healpix(fine)] for m in official])
    shared = np.isfinite(observed).all(axis=1)
    fine, observed = fine[shared], observed[shared]
    which = coarse.skycoord_to_healpix(fine)
    offset = fine.separation(coarse.healpix_to_skycoord(which)).rad
    # Deterministic geometry-only selection. File access and depth differences
    # cannot favor one measurement over another within a coarse cell.
    order = np.lexsort((available[shared], offset, which))
    _, indices = np.unique(which[order], return_index=True)
    pick = order[indices]
    return fine[pick], observed[pick], which[pick], len(available), int(shared.sum())


def aperture_depth(path, ra, dec):
    with fitsio.FITS(path) as f:
        hdu = f[1]
        w = WCS(hdu.read_header())
        x, y = w.all_world2pix(ra, dec, 0)
        pixels_per_arcsec = 1. / (3600. * math_pixel_scale(w))
        r = RADIUS_ARCSEC * pixels_per_arcsec
        a, b = int(np.floor(x - r - 1)), int(np.ceil(x + r + 1))
        c, d = int(np.floor(y - r - 1)), int(np.ceil(y + r + 1))
        ny, nx = hdu.get_info()['dims']
        if min(a, c) < 0 or b > nx or d > ny:
            return np.nan
        ivar = hdu[c:d, a:b].astype(float)
    dx = np.arange(a, b)[:, None] + FRACTION_GRID - x
    dy = np.arange(c, d)[:, None] + FRACTION_GRID - y
    weights = ((dy[:, None, :, None]**2 + dx[None, :, None, :]**2) <= r**2).mean(axis=(2, 3))
    use = weights > 0
    if not np.all(np.isfinite(ivar[use]) & (ivar[use] > 0)):
        return np.nan
    variance = np.sum(weights[use]**2 / ivar[use])
    return 22.5 - 2.5*np.log10(10.*np.sqrt(variance))


def math_pixel_scale(wcs):
    return np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix)))


def run(output, raster):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Read actual survey maps on allocated CPUs')
    data = Path(os.environ['LS_SAT_DATA'])
    root = Path(os.environ['LS_DR11_ROOT'])
    folder = data / 'resources/v14/common_depth/des_y6'
    paths = [folder / f'y6_MAGLIM_decasu_WMEAN_{b}_{NATIVE_DES_NSIDE}_RING.fits.gz' for b in 'gr']
    sky, observed, labels, qualified_centres, shared_centres = sample_sky(
        raster, [des_values(p, b) for p, b in zip(paths, 'gr')])
    icrs = sky.icrs
    bricks = load_bricks(root, 'south')
    tree = cKDTree(unit(bricks['RA'], bricks['DEC']))
    nearest = tree.query(unit(icrs.ra.deg, icrs.dec.deg), k=4)[1]
    names = np.char.strip(bricks['BRICKNAME'].astype('U'))
    file_proof = hashlib.sha256()
    rows = []
    for coord, des, label, candidates in zip(icrs, observed, labels, nearest):
        ra, dec = coord.ra.deg, coord.dec.deg
        for idx in candidates:
            brick = names[idx]
            coadd = root/'south'/'coadd'/brick[:3]/brick
            files = [coadd/f'legacysurvey-{brick}-invvar-{b}.fits.fz' for b in 'gr']
            if not all(file.is_file() for file in files):
                continue
            depths = [aperture_depth(f, ra, dec) for f in files]
            if np.isfinite(depths).all():
                for file in files:
                    stat = file.stat()
                    file_proof.update(f'{file}\t{stat.st_size}\t{stat.st_mtime_ns}\n'.encode())
                break
        else:
            continue
        row = dict(sample_pixel=int(label), ra_deg=ra, dec_deg=dec)
        for b, ls_m, des_m in zip('gr', depths, des):
            row.update({f'ls_{b}_m10': ls_m, f'des_{b}_m10': des_m, f'ls_minus_des_{b}_m10': ls_m-des_m})
        rows.append(row)
    if len(rows) < 30:
        raise ValueError('Insufficient paired DES and LS aperture measurements')
    output.mkdir(parents=True, exist_ok=False)
    table = output/'paired_aperture_depth.csv'
    write_csv(table, rows)
    use = {r['sample_pixel'] for r in rows}
    shown = sky[np.isin(labels, list(use))]
    x, y = -shown.l.wrap_at(180*u.deg).rad, shown.b.rad
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), subplot_kw={'projection':'aitoff'}, layout='constrained')
    values = [np.array([r[f'ls_minus_des_{b}_m10'] for r in rows]) for b in 'gr']
    color_limit = max(.25, np.quantile(np.abs(values), .98))
    summary = {}
    for b, ax, v in zip('gr', axes, values):
        m = ax.scatter(x, y, c=v, vmin=-color_limit, vmax=color_limit, cmap='RdBu_r', s=12, linewidths=0, rasterized=True)
        axes_map(ax, f'{b}-band LS DR11 − DES Y6')
        summary[b] = dict(median=float(np.median(v)), p16_p84=np.quantile(v,[.16,.84]).tolist())
    fig.colorbar(m, ax=axes, label='Observed 10σ image-weight depth difference (mag)', shrink=.68, pad=.045)
    fig.suptitle('Matched formal 2″ diameter aperture depth · DES-assigned qualified DR11 sky')
    save(fig, output/'des_image_depth_difference')
    write_json(output/'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], code_sha256=sha(Path(__file__)),
        official_des_maps={DES_URL+p.name:sha(p) for p in paths},
        frozen_raster_sha256=sha(raster), ls_coadd_file_metadata_sha256=file_proof.hexdigest(),
        wcs_des_only_samples_256=qualified_centres, common_des_gr_map_samples_256=shared_centres, des_min_fracdet=.8,
        selected_sky_samples=len(sky), measured=len(rows), sample_nside=SAMPLE_NSIDE,
        band_statistics=summary, outputs={p.name:sha(p) for p in output.iterdir()},
        scope='Geometry-only equal-area display samples on the DES-assigned qualified footprint. Same 10-sigma observed AB aperture-flux convention. LS variance uses the diagonal inverse variance and subpixel aperture fractions. Pixel covariance and differing weight construction limit strict calibration between the two surveys. Values describe coadd-weight noise, separate from matched-source photometry or effective stellar recovery.'))
    print(dict(measured=len(rows), selected=len(sky), summary=summary), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('raster', type=Path)
    args = p.parse_args()
    run(args.output, args.raster)
