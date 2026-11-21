"""Compare LS to DES DR2 and DELVE DR3 point-source errors on two real skies."""

import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np

from ls_satsearch.data import sample_pixels, select
from ls_satsearch.run import field_cache, sha, write_csv, write_json
from scripts.v13_image_trials import match_to
from scripts.v14_matched_source_depth import q

TAP = 'https://datalab.noirlab.edu/tap/sync'
DIAGNOSTICS = Path('results/v14/census_comparison/missed_controls_manifest.json')
SITES = (
    ('DES DR2', 'des_dr2.main', 'extended_class_coadd', 304.107, -50.33, 'v14_south_des_0128'),
    ('DELVE DR3', 'delve_dr3.coadd_objects', 'ext_xgb', 156.437, -.631, 'v14_south_delve_0620'),
)
RADIUS = .18
LIMIT = 30000


def acquire(folder, table, morph, ra, dec):
    g_r = [f'wavg_mag{e}_psf_{b}' for b in 'gr' for e in ('', 'err')]
    fields = ['ra', 'dec', *g_r, morph]
    width = math.degrees(math.asin(math.sin(math.radians(RADIUS)) / math.cos(math.radians(dec))))
    query = (f"SELECT TOP {LIMIT} {','.join(fields)} FROM {table} WHERE "
             f"ra BETWEEN {ra-width:.8f} AND {ra+width:.8f} AND "
             f"dec BETWEEN {dec-RADIUS:.8f} AND {dec+RADIUS:.8f}")
    data = dict(request='doQuery', lang='ADQL', format='csv', query=query)
    url = TAP + '?' + urlencode(data)
    raw = folder / (table + '.csv')
    if not raw.exists():
        with urlopen(url, timeout=75) as response:
            payload = response.read(10_000_001)
        if len(payload) > 10_000_000:
            raise ValueError('Public cone response exceeded bound')
    else:
        payload = raw.read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if reader.fieldnames != fields:
        raise ValueError(f'Unexpected {table} response schema')
    rows = list(reader)
    if not rows or len(rows) >= LIMIT:
        raise ValueError(f'Cone response empty or at cap for {table}')
    if not raw.exists():
        raw.write_bytes(payload)
    values = np.array([tuple(float(r[k]) if r[k] else np.nan for k in fields) for r in rows],
                      dtype=[(k, 'f8') for k in fields])
    d0, d = math.radians(dec), np.deg2rad(values['dec'])
    chord = np.sin((d - d0) / 2)**2 + np.cos(d) * math.cos(d0) * np.sin(np.deg2rad(values['ra'] - ra) / 2)**2
    inside = chord <= math.sin(math.radians(RADIUS) / 2)**2
    return values[inside], dict(url=url, sha256=sha(raw), count=int(inside.sum()), download_rows=len(rows))


def measure(name, table, morph, ra, dec, ident, diag, root, data, resource):
    source, = [Path(p) for p in diag['inputs'] if p.endswith(f'/{ident}-base/manifest.json')]
    if sha(source) != diag['inputs'][str(source)]:
        raise ValueError('Accepted qualified field changed')
    run = json.loads(source.read_text())
    cfg = run['config']
    field, raw, area, _ = field_cache(root, data, run['field'], cfg, None)
    ref, provenance = acquire(resource, table, morph, ra, dec)
    xy = np.column_stack(field.xy(ref['ra'], ref['dec']))
    ref = ref[area[sample_pixels(field, area, *xy.T)]]
    ref_sky = np.column_stack([ref['ra'], ref['dec']])
    center = field.xy(ra, dec)
    nearby = np.hypot(*(np.column_stack(field.xy(raw['RA'], raw['DEC'])) - center).T) <= RADIUS * 60 + .05
    raw = raw[nearby]
    ls_sky = np.column_stack([raw['RA'], raw['DEC']])
    _, _, _, _, valid = select(raw, field, area, dict(cfg, g_max=99., r_max=99., min_snr=0.))
    found = match_to(ref_sky, ls_sky, .8, field)
    form = found >= 0
    source_rows, ref = raw[found[form]], ref[form]
    point = np.isin(ref[morph], (0, 1)) & valid[found[form]]
    output = []
    for b in 'gr':
        B = b.upper()
        mag, err = (ref[f'wavg_mag{suffix}_psf_{b}'] for suffix in ('', 'err'))
        with np.errstate(invalid='ignore', divide='ignore'):
            snr = (2.5 / math.log(10)) / err
            ls_snr = source_rows[f'FLUX_{B}'] * np.sqrt(source_rows[f'FLUX_IVAR_{B}'])
            dered = 2.5 * np.log10(source_rows[f'MW_TRANSMISSION_{B}'])
            external = mag + 2.5 * np.log10(snr / 10.) + dered
            ls = 22.5 - 2.5 * np.log10(10. / np.sqrt(source_rows[f'FLUX_IVAR_{B}'])) + dered
        keep = point & (mag > 0) & (mag < 40) & (err > 0) & (snr >= 5.) & (snr <= 20.)
        keep &= np.isfinite(external + ls) & (ls_snr >= 5.)
        lo, median, hi = q((ls - external)[keep])
        output.append(dict(survey=name, field=ident, band=b, query_sources=provenance['count'],
            source_centres_in_LS_mask=len(found), astrometric_pairs=int(form.sum()), paired_points=int(keep.sum()),
            LS_m10_median=q(ls[keep])[1], external_m10_median=q(external[keep])[1],
            paired_LS_minus_external_m10_p16=lo, paired_LS_minus_external_m10_median=median,
            paired_LS_minus_external_m10_p84=hi))
    return output, dict(provenance, source_scan_sha256=sha(source))


def run(output):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use an allocated CPU for bounded catalogue access')
    root, data = (Path(os.environ[k]) for k in ('LS_DR11_ROOT', 'LS_SAT_DATA'))
    output.mkdir(parents=True, exist_ok=False)
    resource = data / 'resources/v14/decam_matched_depth'
    resource.mkdir(parents=True, exist_ok=True)
    diag = json.loads(DIAGNOSTICS.read_text())
    rows, sources = [], {}
    for site in SITES:
        result, provenance = measure(*site, diag, root, data, resource)
        rows.extend(result)
        sources[site[0]] = provenance
        print(dict(survey=site[0], paired_points=[r['paired_points'] for r in result]), flush=True)
    csv_path = output / 'matched_dec_am_depth.csv'
    write_csv(csv_path, rows)
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], source_queries=sources,
        code_sha256=sha(Path(__file__)), table_sha256=sha(csv_path),
        scope='Two qualified, 0.18-degree real-sky cones. Matched PSF photometry at 0.8 arcsec, classified as points in both catalogues. Common dereddening at each pair uses the LS DECam transmission for both photometric estimates. Survey magnitudes and errors remain in their native systems. The weighted single-exposure PSF error proxy and LS fit error can differ for shared DECam exposures. These are source-conditional comparisons, not independent sensitivity or an area/completeness estimate.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    run(p.parse_args().output)
