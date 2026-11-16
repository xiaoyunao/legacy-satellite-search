"""Blind conditional catalog injections in real masked development fields."""

import argparse
import json
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree
from scipy.stats import binomtest

from .data import load_bricks, sample_pixels, select
from .run import config_path, coverage_metrics, field_cache, read_csv, settings, write_csv, write_json
from .search import load_isochrone, scan


def choose_sites(field, good, cfg, n, rng):
    sites = []
    f = field.width * 30 - 8
    for _ in range(20000):
        pos = rng.uniform(-f, f, size=2)
        if any(np.linalg.norm(pos - previous) < 21 for previous in sites):
            continue
        if coverage_metrics(field, good, cfg, limit=4, center=pos) < .92:
            continue
        sites.append(pos)
        if len(sites) == n:
            return sites
    raise RuntimeError(f'Only {len(sites)} clean independent injection locations')


def observe(gr, pos, rng, cfg, sample, tree):
    # Nearby observed stars provide an empirical error--magnitude relation.
    by_distance = tree.query(pos, k=min(len(sample), 1800))[1]
    background = sample[np.atleast_1d(by_distance)]
    sg = []
    for b in range(2):
        order = np.argsort(background[:, b+2])
        local_g = background[order, b+2]
        local_sigma = background[order, b+4]
        index = np.searchsorted(local_g, gr[:, b])
        errors = np.array([np.median(local_sigma[max(0, i-25):min(len(local_sigma), i+25)])
                           for i in index])
        # Continue the background-limited relation beyond the sampled faint end.
        errors *= 10**(.4*np.maximum(gr[:, b]-local_g[-1], 0))
        sg.append(errors)
    sig = np.column_stack(sg)
    noisy = gr + rng.normal(size=gr.shape)*sig
    sigma_obs = sig * 10**(.4*(noisy-gr))
    eligible = (np.all(noisy <= [cfg['g_max'], cfg['r_max']], axis=1) &
                np.all(sigma_obs <= 2.5/np.log(10)/cfg['min_snr'], axis=1))
    return noisy, sigma_obs, eligible


def inject_one(pos, distance, rh, count, rng, field, area, cfg, sample, model, tree, *, truncation=7):
    dm = 5 * np.log10(distance) + 10
    mags = model[0] + dm
    # Conditional luminosity function in a window that straddles our catalog cut.
    p = model[1] * (mags[:, 0] <= cfg['g_max']+.4) * (mags[:, 1] <= cfg['r_max']+.4)
    p /= p.sum()
    gr = mags[rng.choice(len(mags), count, p=p)]
    # Finite Plummer aperture keeps different sites from overlapping.
    q = rng.uniform(0, truncation**2/(1+truncation**2), count)
    radial = rh * np.sqrt(q / (1-q))
    theta = rng.uniform(0, 2*np.pi, count)
    xy = pos + np.column_stack([radial*np.cos(theta), radial*np.sin(theta)])
    noisy, sigma_obs, eligible = observe(gr, pos, rng, cfg, sample, tree)
    si, sj = sample_pixels(field, area, *xy.T)
    valid = area[si, sj]
    output = np.column_stack([xy, noisy, sigma_obs])[eligible & valid]
    counts = dict(N_generated=count, N_after_selection=int(eligible.sum()),
                  N_in_valid_area=int(valid.sum()), N_used=len(output))
    return output, dict(x=pos[0], y=pos[1], distance_kpc=distance, dm=dm, rh_arcmin=rh, **counts)


def match_trial(peaks, truth, method, cfg):
    return next((p for p in peaks if p['method'] == method and p.get('branch','main') == 'main' and
                 np.hypot(float(p['x']) - truth['x'], float(p['y']) - truth['y']) <=
                 max(cfg['match_min_arcmin'], truth['rh_arcmin']) and
                 abs(float(p['dm']) - truth['dm']) <= cfg['match_dm_tolerance']), None)


def run(field_id, replicate):
    root, data_root, cfg = settings()
    field_specs = {f['id']: f for f in yaml.safe_load(config_path('fields.yaml').read_text())['fields']}
    spec = field_specs[field_id]
    if spec['role'] != 'pilot_dev':
        raise ValueError('This injection experiment uses development fields')
    field, data, area, _ = field_cache(root, data_root, spec, cfg, load_bricks(root))
    sample, _, _, _, _ = select(data, field, area, cfg)
    model = load_isochrone(data_root/'resources'/cfg['isochrone'])
    reference = read_csv(Path('results/summary') / f'{field_id}-base/deduplicated_peaks.csv')
    rng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], replicate, int(spec['ra'] * 1000)]))
    conditions = [(d, n) for d in (50, 100) for n in (8, 16, 32) for _ in range(2)]
    rng.shuffle(conditions)
    positions = choose_sites(field, area, cfg, len(conditions), rng)
    tree = cKDTree(sample[:, :2])
    trials, stars = [], []
    for pos, (distance, count) in zip(positions, conditions):
        rh = np.rad2deg(np.arctan(.02 / distance)) * 60
        new, truth = inject_one(pos, distance, rh, count, rng, field, area, cfg, sample, model, tree)
        stars.append(new)
        trials.append(truth)
    _, found, seconds, _ = scan(np.concatenate([sample, *stars]), field, area, model, cfg)
    out = []
    for trial in trials:
        for method in ('A','B'):
            peak = match_trial(found, trial, method, cfg) or {}
            baseline = match_trial(reference, trial, method, cfg) or {}
            out.append(dict(field=field_id, replicate=replicate, method=method,
                            **trial, baseline_score=baseline.get('score'), injected_score=peak.get('score'),
                            rank=peak.get('rank'), recovered_dm=peak.get('dm'),
                            offset_arcmin=np.hypot(peak['x']-trial['x'], peak['y']-trial['y']) if peak else None))
    dest = Path('results/summary/injections')
    dest.mkdir(exist_ok=True, parents=True)
    write_csv(dest/f'{field_id}-{replicate}.csv', out)
    write_json(dest/f'{field_id}-{replicate}.json', dict(field=field_id, replicate=replicate,
               seed=cfg['seed'], scan_seconds=seconds))


def combine():
    base = Path('results/summary')
    all_rows = [r for p in sorted((base/'injections').glob('*.csv')) for r in read_csv(p)]
    cuts = json.loads((base/'review_cutoffs.json').read_text())
    tables = []
    for c in [r for r in cuts if r['depth'] == 'base' and r['cutoff'] is not None]:
        for distance in (50, 100):
            for low, high in ((0, 5), (6, 11), (12, 20), (21, 32)):
                subset = [r for r in all_rows if r['method'] == c['method'] and
                          int(r['distance_kpc']) == distance and low <= int(r['N_used']) <= high]
                if not subset:
                    continue
                eligible = [r for r in subset if not r['baseline_score'] or float(r['baseline_score']) < c['cutoff']]
                n = len(eligible)
                recovered = sum(bool(r['injected_score'] and float(r['injected_score']) >= c['cutoff'])
                                for r in eligible)
                ci = binomtest(recovered, n).proportion_ci() if n else None
                tables.append(dict(method=c['method'], budget_per_deg2=c['budget'], distance_kpc=distance,
                                   rh_pc=20, used_member_min=low, used_member_max=high,
                                   total_trials=len(subset), baseline_matches_excluded=len(subset)-n,
                                   evaluated_trials=n, recovered=recovered, fraction=recovered/n if n else None,
                                   conditional_binomial_lo=ci.low if ci else None,
                                   conditional_binomial_hi=ci.high if ci else None))
    if tables:
        write_csv(base/'injection_summary.csv', tables)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('field', nargs='?')
    p.add_argument('replicate', type=int, nargs='?')
    args = p.parse_args()
    if args.field is None:
        combine()
    elif args.replicate is None:
        p.error('replicate is required with a field')
    else:
        run(args.field, args.replicate)
