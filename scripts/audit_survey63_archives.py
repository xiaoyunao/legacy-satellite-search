"""Check public Gemini, HST and HSC-SSP archive metadata at the frozen target."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from astropy.coordinates import CartesianRepresentation, SkyCoord
import astropy.units as u
import yaml

from ls_satsearch.run import write_json


HSC = 'https://hsc-release.mtk.nao.ac.jp/rsrc/pdr3/tract_patches/info/'
FIELDS = ('DUD-COSMOS', 'DUD-DEEP2-3', 'DUD-ELAIS-N1', 'DUD-XMM-LSS',
          'W-AEGIS', 'W-hectomap', 'W-autumn', 'W-spring')
MAST = 'https://mast.stsci.edu/api/v0/invoke'


def get(url, data=None):
    with urlopen(url, data, timeout=45) as response:
        body = response.read(32_000_001)
    if len(body) > 32_000_000:
        raise ValueError(f'Truncated metadata at {url}')
    return body, sha256(body).hexdigest()


def gemini(ra, dec, instrument='GMOS-N'):
    url = f'https://archive.gemini.edu/jsonsummary/ra={ra}/dec={dec}/sr=600/{instrument}/imaging'
    body, digest = get(url)
    rows = json.loads(body)
    if not isinstance(rows, list):
        raise ValueError(f'Unexpected Gemini response for {url}')
    return dict(url=url, sha256=digest, image_metadata_rows=len(rows))


def mast(ra, dec, radius=.105):
    params = dict(position=f'{ra}, {dec}, {radius}', columns='COUNT_BIG(*)',
                  filters=[dict(paramName='obs_collection', values=['HST','JWST']),
                           dict(paramName='dataproduct_type', values=['image'])])
    service = 'Mast.Caom.Filtered.Position'
    query = dict(service=service, params=params, format='json', pagesize=100, page=1)
    body, digest = get(MAST, urlencode({'request': json.dumps(query)}).encode())
    out = json.loads(body)
    rows = out['data']
    if out['status'] != 'COMPLETE' or len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError('Unexpected MAST count response')
    return dict(url=MAST, service=service, params=params, sha256=digest,
                space_telescope_imaging_rows=int(next(iter(rows[0].values()))))


def noirlab(ra, dec):
    url = 'https://astroarchive.noirlab.edu/api/sia/vohdu?' + urlencode(
        dict(POS=f'{ra:.5f},{dec:.5f}', SIZE='.15', VERB=3, format='json'))
    body, digest = get(url)
    summary, *rows = json.loads(body)
    if summary['RESULTS']['MORE'] or summary['RESULTS']['COUNT'] != len(rows):
        raise ValueError('Incomplete NOIRLab HDU query')
    visits = {}
    for row in rows:
        band = row['filter'].split()
        if band and band[0] in ('g', 'gS', "g'") and row['obs_type']=='object':
            key = row['file_dateobs']
            visit = visits.setdefault(key, dict(utc=key, band=row['filter'], seconds=row['exposure'],
                                               instrument=row['instrument'], product_hdu_rows=0,
                                               original_filename=Path(row['original_filename']).name))
            visit['product_hdu_rows'] += 1
    return dict(url=url, sha256=digest, rows=len(rows),
                instruments=sorted({row['instrument'] for row in rows}),
                g_visits=sorted(visits.values(), key=lambda row: row['utc']))


def smoka(center, frame_type, search_radius, date_range=None):
    url = 'https://smoka.nao.ac.jp/HSCsearch'
    params = dict(action='Search', obs_mod='IMAG', data_typ='OBJECT', band='HSC-g',
                  bandwidth_type='FILTER', instruments='HSC', asciitable='Ascii',
                  coordsys='Equatorial', equinox='J2000', output_equinox='J2000',
                  RadOrRec='radius', fieldofview='auto', resolver='NONE',
                  calib_typ='ALL', frameorshot=frame_type, longitudeC=center.ra.to_string(u.hour, sep=':'),
                  latitudeC=center.dec.to_string(u.deg, sep=':', alwayssign=True), radius=search_radius)
    if date_range:
        params['date_obs'] = date_range
    keys = ('FRAMEID', 'DATE_OBS', 'OBJECT', 'FILTER', 'RA2000', 'DEC2000', 'EXPTIME', 'EXP_ID')
    body, digest = get(url, urlencode([*params.items(), *(('dispcol', k) for k in keys)]).encode())
    page = body.decode(errors='replace')
    matches = re.findall(r'^\s*(HSC[AE]\w+)\s+(\d{4}-\d{2}-\d{2})\s+.+?\s+(HSC-\w+)'
                         r'\s+([\d:.]+)\s+([+\-][\d:.]+)\s+([0-9.]+)', page, re.M)
    if len(matches) >= 20000 or (not matches and 'No matching frame' not in page):
        raise ValueError('Unexpected or incomplete SMOKA response')
    g = [m for m in matches if m[2]=='HSC-g']
    angle = [center.separation(SkyCoord(m[3], m[4], unit=(u.hourangle, u.deg))).arcmin for m in g]
    nearest = min(angle) if angle else None
    return dict(url=url, query=params, sha256=digest, parsed_rows=len(matches), g_rows=len(g),
                nearest_g_center_arcmin=float(nearest) if nearest is not None else None)


def hsc_field(name, center, core_radius):
    url = HSC + f'tracts_patches_{name}.txt'
    body, digest = get(url)
    corners = {}
    pat = re.compile(r'^Tract: (\d+)\s+Corner([0-3]) \(RA, Dec\): \(([^,]+), ([^)]+)\)')
    for line in body.decode().splitlines():
        match = pat.match(line)
        if match:
            tract, vertex, ra, dec = match.groups()
            corners.setdefault(tract, {})[int(vertex)] = (float(ra), float(dec))
    if not corners or any(len(each)!=4 for each in corners.values()):
        raise ValueError(f'Incomplete HSC geometry for {name}')
    ids = list(corners)
    vertices = np.array([[corners[t][i] for i in range(4)] for t in ids])
    sky = SkyCoord(vertices[...,0], vertices[...,1], unit='deg')
    # Bound each tract by its maximum vertex separation from its own common centre.
    unit = sky.cartesian.xyz.value.mean(axis=-1)
    midpoint = SkyCoord(CartesianRepresentation(unit), frame='icrs')
    bounds = midpoint[:,None].separation(sky).deg.max(axis=1)
    edge_bound = midpoint.separation(center).deg-bounds
    best = edge_bound.argmin()
    possible = [t for t, value in zip(ids, edge_bound) if value <= core_radius/60]
    return dict(url=url, sha256=digest, tracts=len(ids),
                possible_core_tracts=possible, closest_bound_tract=ids[best],
                closest_tract_bound_arcmin=float(edge_bound[best]*60))


def run(config, output):
    target = yaml.safe_load(config.read_text())
    coord = target['ra_deg'], target['dec_deg']
    center = SkyCoord(*coord, unit='deg')
    radius = target['center_aperture_arcmin']
    cos = SkyCoord(150.1, 2.2, unit='deg')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [pool.submit(hsc_field, field, center, radius) for field in FIELDS]
        control = pool.submit(hsc_field, 'DUD-COSMOS', cos, radius)
        gem = pool.submit(gemini, *coord)
        gem_s = pool.submit(gemini, *coord, 'GMOS-S')
        gem_control = pool.submit(gemini, 53.1625, -27.7914)
        st = pool.submit(mast, *coord)
        noirlab_meta = pool.submit(noirlab, *coord)
        subaru_g = pool.submit(smoka, center, 'Shot', 52)
        subaru_recent = pool.submit(smoka, center, 'Shot', 52, '2024-08-01..2026-11-17')
        st_control = pool.submit(mast, 53.1625, -27.7914, .012)
        write_json(output, dict(ra_dec_deg=coord, core_radius_arcmin=radius,
            hsc_ssp=dict(zip(FIELDS, [job.result() for job in results])),
            hsc_cosmos_control=control.result(), gemini_n=gem.result(), gemini_s=gem_s.result(), mast=st.result(),
            noirlab_expanded=noirlab_meta.result(), smoka_shot=subaru_g.result(),
            smoka_recent_shot=subaru_recent.result(),
            gemini_goods_s_control=gem_control.result(), mast_goods_s_control=st_control.result()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.target, args.output)
