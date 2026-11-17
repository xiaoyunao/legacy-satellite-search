"""Freeze observing-condition strata and North/South comparison pairs before injections."""
from itertools import product
from pathlib import Path

import numpy as np
import yaml
from astropy.coordinates import SkyCoord

from ls_satsearch.run import read_csv, sha, write_csv, write_json

BASE = Path('configs/v12')
DEST = Path('configs/v13/matched')


def inputs(region):
    cohort = 'north' if region == 'north' else 'south_ps1'
    versions = ('v12', 'v11') if region == 'north' else ('v12', 'v12g', 'v11')
    specs = [Path('configs')/v/'cohorts'/cohort/'fields.yaml' for v in versions]
    metric_paths = [Path(f'results/v12/discovery/{v}' if v != 'v11' else 'results/v11')/cohort/'field_metrics.csv'
                    for v in versions]
    base = BASE/'matched'/region/'matched.yaml'
    prior = yaml.safe_load(base.read_text())['fields']
    sky = SkyCoord([r['ra'] for r in prior], [r['dec'] for r in prior], unit='deg')
    conditions = {r['field']: r for path in metric_paths for r in read_csv(path)}
    rows = []
    for f in (row for path in specs for row in yaml.safe_load(path.read_text())['fields']):
        m = conditions.get(f['id'])
        if not m or (float(m['area_deg2']) < .78*f['width']**2):
            continue
        values = [float(m[k]) for k in ('g_depth','r_depth','g_seeing')]
        values.append(np.log10(int(m['inner_psf'])/float(m['area_deg2'])))
        if not np.isfinite(values).all() or SkyCoord(f['ra'], f['dec'], unit='deg').separation(sky).deg.min() < 2.4:
            continue
        rows.append((f, np.array(values)))
    return rows, {str(p): sha(p) for p in (*specs, *metric_paths, base)}


def run():
    south, south_hash = inputs('south')
    north, north_hash = inputs('north')
    planned = []
    used = set()
    metrics = np.array([r[1] for r in south])
    # Pairing weighs absolute differences in measured two-band depths,
    # g seeing and log point-source density on the same scale in both regions.
    scale = np.array([.20, .20, .17, .25])
    all_pairs = sorted((float(np.linalg.norm((s[1]-n[1])/scale)), si, ni)
                       for (si, s), (ni, n) in product(enumerate(south), enumerate(north)))
    for distance, si, ni in all_pairs:
        s, n = south[si], north[ni]
        members = {s[0]['id'], n[0]['id']}
        if members & used:
            continue
        pair = f'pair{1+len(planned)//2}'
        planned.extend([(s, 'south', pair, distance), (n, 'north', pair, distance)])
        used |= members
        if len(planned) == 6:
            break
    # Keep independent backgrounds at four corners of the South depth/seeing plane.
    median = np.median(metrics, axis=0)
    for depth_sign, seeing_sign in product((-1, 1), repeat=2):
        available = [s for s in south if s[0]['id'] not in used]
        mean_depth = lambda x: np.mean(((x-median)/scale)[:2])
        score = lambda r: depth_sign*mean_depth(r[1])+seeing_sign*(r[1][2]-median[2])/scale[2]
        available = [r for r in available if depth_sign*mean_depth(r[1]) >= 0
                     and seeing_sign*(r[1][2]-median[2]) >= 0]
        s = max(available, key=score)
        used.add(s[0]['id'])
        label = f'{"deep" if depth_sign>0 else "shallow"}_{"broad" if seeing_sign>0 else "sharp"}'
        planned.append((s,'south',label,None))
    table = []
    for region in ('north', 'south'):
        cfg = yaml.safe_load((BASE/'matched'/region/'matched.yaml').read_text())
        cfg['fields'] = []
        for (f, m), sector, pair, offset in planned:
            if sector != region:
                continue
            field_id = 'v13_select_' + f['id']
            cfg['fields'].append(dict(id=field_id, role='pilot_eval', survey=3, ra=f['ra'], dec=f['dec']))
            table.append(dict(field=field_id, region=region, stratum=pair, ra_deg=f['ra'], dec_deg=f['dec'],
                              g_depth=m[0], r_depth=m[1], seeing=m[2], log_psf_density=m[3],
                              normalized_pair_difference=offset))
        target = DEST/region
        target.mkdir(parents=True, exist_ok=True)
        (target/'matched.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
        (target/'search.yaml').write_bytes((BASE/'matched'/region/'search.yaml').read_bytes())
    write_csv(DEST/'strata.csv', table)
    write_json(DEST/'design.json', dict(source_hashes=north_hash | south_hash, matching_scales=scale.tolist(),
               minimum_production_area_fraction=.78, minimum_separation_from_round12_matched_deg=2.4))


if __name__ == '__main__':
    run()
