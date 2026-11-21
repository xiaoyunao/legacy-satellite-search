"""Sample common DR11 and DELVE DR3 aperture depths from public coadd weights."""

import argparse
from collections import defaultdict
import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlsplit
from xml.etree import ElementTree

from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
from astropy.wcs import WCS
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import load_bricks
from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_des_image_depth import FRACTION_GRID, MAP_NSIDE, aperture_depth, math_pixel_scale
from scripts.v14_ps1_image_depth import fits_image, retrieve
from scripts.v14_qualified_aitoff import axes_map, save

SIA = 'https://datalab.noirlab.edu/sia/delve_dr3'
SAMPLE_NSIDE = 8


def select_points(path, tile_index):
    fine = HEALPix(nside=MAP_NSIDE, frame='galactic', order='ring')
    coarse = HEALPix(nside=SAMPLE_NSIDE, frame='galactic', order='ring')
    with np.load(path) as raster:
        accepted = (raster['bits'] == 4) & (raster['regions'] == 1)
    if tile_index is None:
        coords = fine.healpix_to_skycoord(np.flatnonzero(accepted))
    else:
        bands = defaultdict(set)
        for row in read_csv(tile_index):
            bands[float(row['s_ra']), float(row['s_dec'])].add(row['obs_bandpass'])
        positions = [k for k, b in bands.items() if {'g','r'} <= b]
        ra, dec = np.array(positions).T
        coords = SkyCoord(ra, dec, unit='deg')
        coords = coords[accepted[fine.skycoord_to_healpix(coords)]]
    group = coarse.skycoord_to_healpix(coords)
    nearest = coords.separation(coarse.healpix_to_skycoord(group)).rad
    order = np.lexsort((coords.icrs.dec.deg, coords.icrs.ra.deg, nearest, group))
    _, indices = np.unique(group[order], return_index=True)
    return [(int(group[i]), coords[i].icrs) for i in order[indices]]


def discover(coord, path):
    params = dict(POS=f'{coord.ra.deg:.9f},{coord.dec.deg:.9f}', SIZE='.01', FORMAT='image/fits')
    body = retrieve(f'{SIA}?{urlencode(params)}', path, limit=4_000_000)
    root = ElementTree.fromstring(body)
    table = root.find('.//TABLE')
    if table is None:
        raise ValueError('No SIA table')
    fields = [node.attrib['name'] for node in table.findall('FIELD')]
    options = {}
    for row in table.iter('TR'):
        values = dict(zip(fields, [node.text or '' for node in row]))
        band = values['obs_bandpass']
        kind = values['prodtype']
        if values['proctype'] != 'Stack' or band not in ('g', 'r') or kind not in ('image', 'mask', 'weight'):
            continue
        url = values['access_url']
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != 'datalab.noirlab.edu' or parsed.path != '/svc/cutout':
            continue
        dataset = parse_qs(parsed.query)['siaRef'][0]
        suffix = f'_{band}.fits.fz'
        if dataset.endswith(suffix):
            options.setdefault(dataset.removesuffix(suffix), {})[band, kind] = url
    return [(k, v) for k, v in sorted(options.items()) if len(v) == 6]


def delve_depth(path, coord):
    images = {k: fits_image(f) for k, f in path.items()}
    science, image = images['image']
    w, weight = images['weight']
    m, mask = images['mask']
    if science['EXTNAME'] != 'SCI' or w['EXTNAME'] != 'WGT' or m['EXTNAME'] != 'MSK':
        raise ValueError('Unexpected DR3 coadd extensions')
    if not np.isfinite(science['MAGZERO']) or science['BUNIT'] != 'COUNTS/S':
        raise ValueError('Unexpected DELVE image photometric units')
    if image.shape != weight.shape or image.shape != mask.shape:
        raise ValueError('DR3 image, weight and mask shapes differ')
    centres = [WCS(h).all_world2pix(coord.ra.deg, coord.dec.deg, 0) for h in (science, w, m)]
    if not np.allclose(centres, centres[0], atol=.001):
        raise ValueError('DR3 extension WCS centres differ')
    x, y = centres[0]
    yy, xx = np.indices(image.shape)
    radius = 1. / (3600 * math_pixel_scale(WCS(science)))
    dx = xx[:, :, None] + FRACTION_GRID - x
    dy = yy[:, :, None] + FRACTION_GRID - y
    aperture = ((dy[:, :, :, None]**2 + dx[:, :, None, :]**2) <= radius**2).mean(axis=(2, 3))
    relevant = aperture > 0
    if (not relevant.any() or np.any(relevant[[0, -1], :]) or np.any(relevant[:, [0, -1]])
            or not np.all(np.isfinite(image[relevant]) & (weight[relevant] > 0)
                          & np.isfinite(weight[relevant]) & (mask[relevant] == 0))):
        return np.nan
    variance = np.sum(aperture[relevant]**2 / weight[relevant])
    return science['MAGZERO'] - 2.5 * np.log10(10 * np.sqrt(variance))


def evaluate(task, folder, dr11, tree, names):
    pixel, coord = task
    signature = hashlib.sha256(f'{coord.ra.deg:.9f},{coord.dec.deg:.9f}'.encode()).hexdigest()[:12]
    stash = folder / f'hpx{pixel:04d}-{signature}'
    stash.mkdir(exist_ok=True)
    try:
        options = discover(coord, stash / 'sia.xml')
        for identifier, links in options:
            files = {}
            for (b, k), url in links.items():
                files[b, k] = stash / f'{identifier}-{b}-{k}.fits'
                retrieve(url, files[b, k])
            delve = [delve_depth({k:p for (band,k),p in files.items() if band == b}, coord) for b in 'gr']
            if np.isfinite(delve).all():
                break
        else:
            return dict(sample_pixel=pixel, status='no_public_valid_gr_aperture')
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as error:
        return dict(sample_pixel=pixel, status='acquisition_or_schema_failure', detail=str(error)[:220])
    candidates = tree.query(unit([coord.ra.deg],[coord.dec.deg]), k=4)[1][0]
    for j in candidates:
        brick = names[j]
        paths = [dr11/'south'/'coadd'/brick[:3]/brick/f'legacysurvey-{brick}-invvar-{b}.fits.fz' for b in 'gr']
        if not all(p.is_file() for p in paths):
            continue
        ls = [aperture_depth(p, coord.ra.deg, coord.dec.deg) for p in paths]
        if np.isfinite(ls).all():
            break
    else:
        return dict(sample_pixel=pixel, status='no_valid_LS_gr_aperture')
    record = dict(sample_pixel=pixel, status='measured', ls_brick=brick, delve_tile=identifier,
                  ra_deg=coord.ra.deg, dec_deg=coord.dec.deg, gal_l_deg=coord.galactic.l.deg,
                  gal_b_deg=coord.galactic.b.deg, source_sha256='|'.join(sha(p) for _,p in sorted(files.items())))
    for b, ls_depth, delve_mag in zip('gr', ls, delve):
        record.update({f'ls_{b}_m10':ls_depth, f'delve_{b}_m10':delve_mag,
                       f'ls_minus_delve_{b}_m10':ls_depth - delve_mag})
    return record


def run(output, raster, limit, tile_index):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use an allocated CPU for processing public images')
    root = Path(os.environ['LS_DR11_ROOT'])
    data = Path(os.environ['LS_SAT_DATA'])
    folder = data/'resources/v14/common_depth/delve_sample'
    folder.mkdir(parents=True, exist_ok=True)
    points = select_points(raster, tile_index)
    chosen = points if limit is None else [points[i] for i in np.linspace(0,len(points)-1,limit,dtype=int)]
    bricks = load_bricks(root,'south')
    tree = cKDTree(unit(bricks['RA'],bricks['DEC']))
    names = np.char.strip(bricks['BRICKNAME'].astype('U'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda t: evaluate(t, folder, root, tree, names), chosen))
    measured = [r for r in rows if r['status'] == 'measured']
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output/'unavailable_samples.csv', [r for r in rows if r['status'] != 'measured'],
              keys=('sample_pixel', 'status', 'detail'))
    summary = {}
    if measured:
        write_csv(output/'paired_aperture_depth.csv', measured)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), subplot_kw={'projection':'aitoff'}, layout='constrained')
        delta = [np.array([r[f'ls_minus_delve_{b}_m10'] for r in measured]) for b in 'gr']
        extent = max(.25, np.quantile(np.abs(delta), .98))
        l = -((np.array([r['gal_l_deg'] for r in measured]) + 180) % 360 - 180)
        x, y = np.deg2rad(l), np.deg2rad([r['gal_b_deg'] for r in measured])
        for b, a, d in zip('gr', axes, delta):
            marker = a.scatter(x, y, c=d, cmap='RdBu_r', s=13, vmin=-extent, vmax=extent,
                               linewidths=0, rasterized=True)
            axes_map(a, f'{b}-band LS DR11 − DELVE DR3')
            summary[b] = dict(median=float(np.median(d)), p16_p84=np.quantile(d,[.16,.84]).tolist())
        fig.colorbar(marker, ax=axes, label='Observed 10σ image-weight depth difference (mag)', shrink=.68)
        fig.suptitle('Matched formal 2″ diameter aperture depth · DELVE-assigned qualified DR11 sky')
        save(fig, output/'delve_image_depth_difference')
    write_json(output/'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], sia=SIA,
        raster_sha256=sha(raster), tile_index_sha256=sha(tile_index) if tile_index else None, code_sha256=sha(Path(__file__)), sample_nside=SAMPLE_NSIDE,
        candidate_points=len(points), attempted=len(chosen), measured=len(measured), band_statistics=summary,
        outputs={p.name:sha(p) for p in output.iterdir()},
        scope='Public DELVE DR3 standard SCI/MSK/WGT cutouts, using SCI MAGZERO and positive inverse variance in the unflagged shared aperture. Empty SIA responses remain unavailable. Diagonal noise only, without covariance or stellar completeness. Equal-area sample centres do not imply coverage of complete cells.'))
    print(dict(attempted=len(chosen), measured=len(measured), band_statistics=summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('raster', type=Path)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--tile-index', type=Path)
    args = parser.parse_args()
    run(args.output, args.raster, args.limit, args.tile_index)
