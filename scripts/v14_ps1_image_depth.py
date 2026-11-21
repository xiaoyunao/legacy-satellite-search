"""Measure matched LS and PS1 aperture noise using native stack variance cutouts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table
from astropy_healpix import HEALPix
from astropy.wcs import WCS
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import load_bricks, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.run import sha, write_csv, write_json
from scripts.v14_des_image_depth import FRACTION_GRID, MAP_NSIDE, aperture_depth, math_pixel_scale
from scripts.v14_qualified_aitoff import axes_map, save

SERVICE = 'https://ps1images.stsci.edu/cgi-bin/'
SAMPLE_NSIDE = 8
NPIX_CUTOUT = 48
NATIVE_REFERENCE = Path('results/v14/ps1_ipp/blank_pilot/images_acquisition.json')


def retrieve(url, path, limit=1_000_000):
    if path.exists():
        return path.read_bytes()
    with urlopen(url, timeout=35) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError('PS1 response exceeded configured size')
    pending = path.with_suffix(path.suffix+'.partial')
    pending.write_bytes(body)
    pending.rename(path)
    return body


def cutout(file, coord, target):
    url = SERVICE + 'fitscut.cgi?' + urlencode(dict(ra=f'{coord.ra.deg:.9f}', dec=f'{coord.dec.deg:.9f}',
        size=NPIX_CUTOUT, format='fits', red=file))
    retrieve(url, target)
    return target


def fits_image(file):
    with fits.open(file, memmap=False) as ff:
        image = next(h for h in ff if h.header.get('NAXIS') == 2)
        return image.header.copy(), image.data.copy()


def verify_native(reference):
    record = json.loads(NATIVE_REFERENCE.read_text())
    sky = SkyCoord(float(record['site']['ra_deg'])*u.deg, float(record['site']['dec_deg'])*u.deg)
    residual = {}
    for b in 'gr':
        item = next(p for p in record['products'] if p['filter'] == b and p['type'] == 'stack.wt')
        source = Path(item['path'])
        if sha(source) != item['sha256']:
            raise ValueError('Existing native reference stack changed')
        cut = cutout(item['filename'], sky, reference / f'native_reference_{b}.fits')
        hdr, v = fits_image(cut)
        with fits.open(source, memmap=False) as ff:
            h = next(h for h in ff if h.header.get('NAXIS') == 2)
            if int(h.header['STK_ID']) != int(hdr['STK_ID']) or h.header['EXPTIME'] != hdr['EXPTIME']:
                raise ValueError('Cutout does not bind the same PS1 native stack')
            y, x = np.indices(v.shape)
            sx, sy = WCS(h.header).all_world2pix(*WCS(hdr).all_pix2world(x, y, 0), 0)
            ix, iy = np.rint(sx).astype(int), np.rint(sy).astype(int)
            if max(abs(sx-ix).max(), abs(sy-iy).max()) > .01:
                raise ValueError('PS1 cutout and native pixel coordinates differ')
            x0, y0 = ix.min(), iy.min()
            patch = h.section[y0:iy.max()+1,x0:ix.max()+1][iy-y0,ix-x0]
            native = h.header['BOFFSET'] + 2*h.header['BSOFTEN']*np.sinh(patch/1.0857362)
        ok = np.isfinite(v) & np.isfinite(native) & (native > 0)
        if ok.sum() < 100:
            raise ValueError('Not enough comparable pixels in the actual native reference')
        relative = np.abs(v[ok]-native[ok])/native[ok]
        if np.quantile(relative,.95) > .005:
            raise ValueError('The PS1 variance cutout does not recover original variance units')
        residual[b] = dict(native_stack_sha256=item['sha256'], cutout_sha256=sha(cut), pixels=int(ok.sum()),
                           p95_relative_error=float(np.quantile(relative,.95)), stack_id=int(hdr['STK_ID']))
    return residual


def ps1_aperture_depth(file, coord):
    hdr, variance = fits_image(file)
    w = WCS(hdr)
    if hdr.get('BSOFTEN') is not None:
        raise ValueError('Expected the service to linearize PS1 variance')
    x, y = w.all_world2pix(coord.ra.deg, coord.dec.deg, 0)
    px_radius = 1. / (3600. * math_pixel_scale(w))
    yy, xx = np.indices(variance.shape)
    dx = xx[:, :, None] + FRACTION_GRID - x
    dy = yy[:, :, None] + FRACTION_GRID - y
    weights = ((dy[:, :, :, None]**2 + dx[:, :, None, :]**2) <= px_radius**2).mean(axis=(2,3))
    relevant = weights > 0
    if (not np.all(np.isfinite(variance[relevant]) & (variance[relevant] > 0))
            or np.any(relevant[0]) or np.any(relevant[-1]) or np.any(relevant[:,0]) or np.any(relevant[:,-1])):
        return np.nan
    return 25. + 2.5 * math.log10(hdr['EXPTIME']) - 2.5 * np.log10(
        10. * np.sqrt(np.sum(weights[relevant]**2*variance[relevant])))


def select_points(raster):
    fine = HEALPix(nside=MAP_NSIDE, frame='galactic', order='ring')
    coarse = HEALPix(nside=SAMPLE_NSIDE, frame='galactic', order='ring')
    with np.load(raster) as table:
        pixels = np.flatnonzero(table['bits'] == 8)
        coords = fine.healpix_to_skycoord(pixels)
        regions = table['regions'][pixels]
    labels = coarse.skycoord_to_healpix(coords)
    offset = coords.separation(coarse.healpix_to_skycoord(labels)).rad
    order = np.lexsort((pixels, offset, labels))
    _, k = np.unique(labels[order], return_index=True)
    kept = order[k]
    result = {}
    for i in kept:
        xy = coords[i].icrs
        north = regions[i] == 2 or (regions[i] == 3 and regional_primary(xy.ra.deg,xy.dec.deg,'north'))
        result[int(labels[i])] = (xy, 'north' if north else 'south')
    return result


def evaluate(point, brick_index, download, root):
    ident, (coord, region) = point
    root_local = download / f'hpx{ident:04d}'
    root_local.mkdir(exist_ok=True)
    url = SERVICE + 'ps1filenames.py?' + urlencode(dict(ra=f'{coord.ra.deg:.9f}',dec=f'{coord.dec.deg:.9f}',
        filters='gr',type='stack.wt'))
    try:
        body = retrieve(url, root_local/'listing.txt')
        table = Table.read(body.decode().splitlines(), format='ascii.basic', guess=False)
        cells = {}
        for row in table:
            key = int(row['projcell']), int(row['subcell'])
            cells.setdefault(key, {})[str(row['filter'])] = str(row['filename'])
        for key, cell in sorted(cells.items()):
            if 'g' not in cell or 'r' not in cell:
                continue
            paths = [cutout(cell[b],coord,root_local/f'{key[0]}-{key[1]}-{b}.fits') for b in 'gr']
            ps = [ps1_aperture_depth(path,coord) for path in paths]
            if np.isfinite(ps).all():
                break
        else:
            return dict(sample_pixel=ident,status='missing_valid_PS1_gr')
    except (OSError,ValueError) as exc:
        return dict(sample_pixel=ident,status='PS1_acquisition_or_schema_error', detail=str(exc)[:180])
    tree, names = brick_index[region]
    neighbors = np.asarray(tree.query(unit([coord.ra.deg],[coord.dec.deg]), k=4)[1]).reshape(-1)
    for j in neighbors:
        brick = names[j]
        paths_ls = [root/region/'coadd'/brick[:3]/brick/f'legacysurvey-{brick}-invvar-{b}.fits.fz' for b in 'gr']
        if not all(f.is_file() for f in paths_ls):
            continue
        ls = [aperture_depth(path,coord.ra.deg,coord.dec.deg) for path in paths_ls]
        if np.isfinite(ls).all():
            break
    else:
        return dict(sample_pixel=ident,status='missing_valid_LS_gr')
    result = dict(sample_pixel=ident,status='measured',ra_deg=coord.ra.deg,dec_deg=coord.dec.deg,
        gal_l_deg=coord.galactic.l.deg,gal_b_deg=coord.galactic.b.deg,ls_region=region,
        cutout_sha256='|'.join(sha(p) for p in paths), ls_brick=brick)
    for b, m_ls, m_ps in zip('gr',ls,ps):
        result.update({f'ls_{b}_m10':m_ls,f'ps1_{b}_m10':m_ps,f'ls_minus_ps1_{b}_m10':m_ls-m_ps})
    return result


def run(output, raster, limit):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use an allocated CPU and scratch for public cutouts')
    data = Path(os.environ['LS_SAT_DATA'])
    root = Path(os.environ['LS_DR11_ROOT'])
    folder = data/'resources/v14/common_depth/ps1_sample'
    folder.mkdir(parents=True,exist_ok=True)
    reference = verify_native(folder)
    points = select_points(raster)
    # A three-point preregistered smoke sample spans the PS1 sky. The full run
    # preserves the deterministic one-point-per-coarse-cell design.
    tasks = list(points.items())
    if limit:
        tasks = [tasks[i] for i in np.linspace(0,len(tasks)-1,limit,dtype=int)]
    indices = {}
    inputs = {}
    for region in ('north','south'):
        bricks = load_bricks(root,region)
        path = root/region/f'survey-bricks-dr11-{region}.fits.gz'
        inputs[str(path)] = sha(path)
        indices[region] = (cKDTree(unit(bricks['RA'],bricks['DEC'])),np.char.strip(bricks['BRICKNAME'].astype('U')))
    output.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda t: evaluate(t,indices,folder,root), tasks))
    measured = [r for r in rows if r['status']=='measured']
    if not measured:
        raise ValueError('No valid matched aperture comparisons')
    write_csv(output/'paired_aperture_depth.csv',measured)
    failures = [r for r in rows if r['status']!='measured']
    if failures:
        write_csv(output/'unavailable_samples.csv',failures)
    fig, axes = plt.subplots(1,2,figsize=(12,4.4),subplot_kw={'projection':'aitoff'},layout='constrained')
    v = [np.array([r[f'ls_minus_ps1_{b}_m10'] for r in measured]) for b in 'gr']
    l = -((np.array([r['gal_l_deg'] for r in measured]) + 180) % 360 - 180)
    x,y = np.deg2rad(l), np.deg2rad([r['gal_b_deg'] for r in measured])
    scale = max(.25,np.quantile(np.abs(v),.98))
    summary = {}
    for b,ax,a in zip('gr',axes,v):
        artist = ax.scatter(x,y,c=a,cmap='RdBu_r',vmin=-scale,vmax=scale,s=13,linewidths=0,rasterized=True)
        axes_map(ax,f'{b}-band LS DR11 − PS1 stack')
        summary[b] = dict(median=float(np.median(a)), p16_p84=np.quantile(a,[.16,.84]).tolist())
    fig.colorbar(artist,ax=axes,label='Observed 10σ image-weight depth difference (mag)',shrink=.68)
    fig.suptitle('Matched formal 2″ diameter aperture depth · PS1-assigned qualified DR11 sky')
    save(fig,output/'ps1_image_depth_difference')
    write_json(output/'manifest.json',dict(job=os.environ['SLURM_JOB_ID'], native_variance_verification=reference,
        raster_sha256=sha(raster), ls_brick_table_sha256=inputs, sample_nside=SAMPLE_NSIDE, candidate_points=len(points),
        attempted=len(rows), measured=len(measured), band_statistics=summary,
        code_sha256=sha(Path(__file__)), outputs={p.name:sha(p) for p in output.iterdir()},
        scope='Common formal observed AB aperture depth from positive diagonal variance. PS1 native variance scale is verified against same pixels in acquired full stacks. Public cutout masks are unavailable as usable bit images, so PS1 positions use the accepted census WCS mask and finite positive variance over the aperture. LS uses its own native passbands. Covariance and source completeness are outside the measured image-weight statistic.'))
    print(dict(attempted=len(rows),measured=len(measured),summary=summary),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('raster',type=Path)
    p.add_argument('--limit',type=int)
    a = p.parse_args()
    run(a.output,a.raster,a.limit)
