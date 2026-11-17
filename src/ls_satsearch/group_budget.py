"""Calibrate discovery to sky groups and score truth-blind representatives."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from scipy.spatial import cKDTree

from .hypotheses import truth_branch
from .run import read_csv, write_csv, write_json

POLICIES = {
    'A_base': ('A_base',),
    'A_deep': ('A_deep',),
    'B_base': ('B_base',),
    'B_deep': ('B_deep',),
    'A_union': ('A_base', 'A_deep'),
    'AB_union': ('A_base', 'A_deep', 'B_base', 'B_deep'),
}


def groups(rows):
    """Rank-first anchored groups; fainter hypotheses cannot move the anchor."""
    rows = sorted(rows, key=lambda r: (-r['ranking'], r['channel'], r['dm'], r['rh_arcmin'],
                                       r['x'], r['y']))
    if not rows:
        return []
    xy = np.array([(r['x'], r['y']) for r in rows])
    rh = np.array([r['rh_arcmin'] for r in rows])
    tree = cKDTree(xy)
    used = np.zeros(len(rows), dtype=bool)
    result = []
    for i in range(len(rows)):
        if used[i]:
            continue
        neighbors = np.asarray(tree.query_ball_point(xy[i], max(1., rh[i])), dtype=int)
        neighbors = neighbors[~used[neighbors]]
        dist = np.linalg.norm(xy[neighbors] - xy[i], axis=1)
        linked = neighbors[dist <= np.maximum(1., np.minimum(rh[i], rh[neighbors]))]
        used[linked] = True
        result.append((rows[i], [rows[j] for j in sorted(linked)]))
    return result


def cut(scores, area, budget):
    scores = sorted(scores, reverse=True)
    target = math.floor(area * budget)
    if not target or not scores:
        return None, target
    if len(scores) <= target:
        return float(scores[-1]), target
    return float(np.nextafter(scores[target], np.inf)), target


def matches(items, truth, cutoff, cfg):
    true_dm = 5 * math.log10(float(truth['D_kpc'])) + 10
    target = SkyCoord(float(truth['ra_deg']), float(truth['dec_deg']), unit='deg')
    radius = max(cfg['match_min_arcmin'], cfg['match_rh_factor'] * float(truth['theta_h_arcmin']))
    for anchor, alternatives in items:
        if cutoff is None or anchor['ranking'] < cutoff:
            break
        position = SkyCoord(anchor['ra_deg'], anchor['dec_deg'], unit='deg')
        offset = target.separation(position).arcmin
        if offset > radius:
            continue
        qualifying = [r for r in alternatives if r['ranking'] >= cutoff and
                      target.separation(SkyCoord(r['ra_deg'], r['dec_deg'], unit='deg')).arcmin <= radius]
        correct = [r for r in qualifying if abs(r['dm'] - true_dm) <= .25]
        return dict(spatial=True, blind_dm=anchor['dm'], blind_dm_error=anchor['dm']-true_dm,
                    blind_correct=abs(anchor['dm']-true_dm) <= .25,
                    correct_mode_exists=bool(correct), correct_mode_dm=correct[0]['dm'] if correct else None,
                    wide_mode_exists=any(abs(r['dm']-true_dm) <= cfg['match_dm_tolerance'] for r in qualifying),
                    offset_arcmin=float(offset), representative_channel=anchor['channel'])
    return dict(spatial=False, blind_correct=False, correct_mode_exists=False, wide_mode_exists=False)


def load_runs(summary, branch):
    fields = {}
    for path in sorted(summary.glob('*/manifest.json')):
        manifest = json.loads(path.read_text())
        if manifest['status'] != 'complete':
            continue
        spec = manifest['field']
        field = fields.setdefault(spec['id'], dict(spec=spec, manifests={}, channels={}, coverage={}))
        depth = manifest['depth']
        field['manifests'][depth] = manifest
        recovery_path = path.parent / 'recovery.csv'
        if recovery_path.exists():
            coverage = read_csv(recovery_path)
            if coverage:
                field['coverage'][depth] = coverage[0]['covered'] == 'True'
        path = path.parent / 'deduplicated_peaks.csv'
        for method in manifest['config'].get('methods', ('A', 'B')):
            field['channels'].setdefault(f'{method}_{depth}', [])
        for row in read_csv(path):
            if row['branch'] != branch:
                continue
            channel = f"{row['method']}_{depth}"
            values = {k: float(row[k]) for k in ('x','y','ra_deg','dec_deg','dm','rh_arcmin','score')}
            for key in ('raw_peak_id', 'n_on', 'n_off', 'area_on_arcmin2', 'area_off_arcmin2'):
                if row.get(key):
                    values[key] = float(row[key])
            field['channels'][channel].append(dict(values, channel=channel,
                                                   peak_rank=int(row['rank'])))
    return fields


def evaluate(summary, output, branch='main', archive=False, apply=None, expected_dev=None,
             channels_only=None, analysis_roles=None):
    fields = load_runs(summary, branch)
    if analysis_roles:
        for name, field in fields.items():
            if name in analysis_roles:
                field['spec'] = dict(field['spec'], role=analysis_roles[name])
    if not fields:
        raise ValueError('No completed runs')
    if expected_dev is not None:
        observed = {name for name, field in fields.items()
                    if field['spec']['role'] == 'pilot_dev'
                    and {'base', 'deep'} <= field['manifests'].keys()}
        if observed != set(expected_dev):
            raise ValueError(f'Unexpected completed baseline/deep development cohort: {sorted(observed)}')
        if any(f['spec']['role'] == 'pilot_eval' for f in fields.values()):
            raise ValueError('Development calibration must precede processing the evaluation cohort')
    if channels_only:
        fields = {name:f for name,f in fields.items()
                  if set(channels_only) <= f['channels'].keys()}
        if not fields:
            raise ValueError('No fields with all requested channels')
    output.mkdir(parents=True, exist_ok=True)
    truths = {r['name']: r for r in read_csv(Path('references/benchmarks.csv'))}
    development = [f for f in fields.values() if f['spec']['role'] == 'pilot_dev']
    evaluation = [f for f in fields.values() if f['spec']['role'] == 'pilot_eval']
    records, blocks, recovery, candidates, frozen = [], [], [], [], []
    first = next(iter(fields.values()))
    cfg = next(iter(first['manifests'].values()))['config']
    recipe = {k:v for k,v in cfg.items() if k not in ('methods','method_fields','g_max','r_max')}
    limits = {depth:{k:next(f['manifests'][depth]['config'][k] for f in fields.values()
                            if depth in f['manifests']) for k in ('g_max','r_max')}
              for depth in ('base','deep') if any(depth in f['manifests'] for f in fields.values())}
    for field in fields.values():
        for depth,m in field['manifests'].items():
            used = m['config']
            if any(used[k] != v for k,v in {**recipe,**limits[depth]}.items()):
                raise ValueError('Inconsistent scan recipe or photometric limits within the cohort')
    bounds_path = summary / 'prefix_bounds.json'
    bounds = json.loads(bounds_path.read_text()) if bounds_path.exists() else {}
    if apply is None:
        if not development:
            raise ValueError('Candidate cost calibration requires completed development fields')
        shared_channels = set.intersection(*(set(f['channels']) for f in development))
        scales = {}
        for name in sorted(shared_channels):
            scores = [p[0]['ranking'] for f in development
                      for p in groups([dict(r, ranking=r['score']) for r in f['channels'][name]])]
            area = sum(f['manifests'][name.split('_')[1]]['area_deg2'] for f in development)
            scale, _ = cut(scores, area, .3)
            if scale is not None and scale > 0:
                scales[name] = scale
        cases = [(policy, channels, budget, None) for policy, channels in POLICIES.items()
                 if set(channels) <= shared_channels and (len(channels) == 1 or set(channels) <= scales.keys())
                 for budget in cfg['review_budgets_deg2']]
    else:
        spec = json.loads(apply.read_text())
        if spec['branch'] != branch or spec['recipe'] != recipe or spec['limits'] != limits:
            raise ValueError('Frozen policy has a different branch, recipe or photometric limits')
        scales = spec['scales']
        cases = [(r['policy'], tuple(r['channels']), r['budget'], r) for r in spec['thresholds']]
    cached = {}
    for policy, channels, budget, previous in cases:
        def per_field(field):
            key = (field['spec']['id'], policy)
            if key in cached:
                return cached[key]
            if any(c not in field['channels'] for c in channels):
                return None
            areas = [field['manifests'][c.split('_')[1]]['area_deg2'] for c in channels]
            if not np.allclose(areas, areas[0], atol=1e-9, rtol=0):
                raise ValueError('Policy channels have unequal area for the same sky field')
            rows = [dict(r, ranking=r['score'] / scales[c] if len(channels) > 1 else r['score'])
                    for c in channels for r in field['channels'][c]]
            cached[key] = (areas[0], groups(rows))
            return cached[key]

        results = [(field, *val) for field in fields.values() if (val := per_field(field)) is not None]
        dev = [(a, g) for f,a,g in results if f['spec']['role']=='pilot_dev']
        area = sum(a for a,_ in dev)
        if previous is None:
            cutoff, target = cut([anchor['ranking'] for _,g in dev for anchor,_ in g], area, budget)
        else:
            cutoff, target = previous['cutoff'], previous['target']
        frozen.append(dict(policy=policy, channels=channels, budget=budget, cutoff=cutoff, target=target))
        for field, area, items in results:
            sky = field['spec']
            for channel in channels:
                bound = bounds.get(sky['id'], {}).get(channel)
                if bound is not None:
                    scaled = bound / scales[channel] if len(channels)>1 else bound
                    if cutoff is None or scaled >= cutoff:
                        raise ValueError(f"Prefix too short for {sky['id']} {channel} {budget}")
            kept = [(anchor, rest) for anchor,rest in items if cutoff is not None and anchor['ranking']>=cutoff]
            count = len(kept)
            hypotheses = sum(sum(r['ranking']>=cutoff for r in rest) for _,rest in kept)
            blocks.append(dict(policy=policy, branch=branch, budget=budget, field=sky['id'], role=sky['role'],
                               area_deg2=area, kept_sky_groups=count, passing_hypotheses=hypotheses, cutoff=cutoff))
            if sky.get('truth'):
                truth = truths[sky['truth']]
                if truth_branch(float(truth['D_kpc'])) == branch:
                    covered = all(field['coverage'].get(c.split('_')[1],True) for c in channels)
                    status = matches(kept,truth,cutoff,cfg) if covered else dict(
                        spatial=False,blind_correct=False,correct_mode_exists=False)
                    recovery.append(dict(policy=policy,budget=budget,name=sky['truth'],field=sky['id'],
                                         covered=covered,**status))
            elif sky['role'] in ('pilot_dev','pilot_eval'):
                for idx,(anchor,rest) in enumerate(kept,1):
                    group_id=f"{sky['id']}-{policy}-{budget}-{idx:03d}"
                    candidates.extend(dict(row, field=sky['id'], role=sky['role'], policy=policy,budget=budget,
                                           group_id=group_id, representative=(row is anchor),
                                           passes_group_cut=row['ranking']>=cutoff) for row in rest
                                      if row['ranking']>=cutoff)
        count = lambda role: sum(r['kept_sky_groups'] for r in blocks if
            (r['policy'],r['budget'],r['role'])==(policy,budget,role))
        valid = [r for r in recovery if (r['policy'],r['budget'])==(policy,budget) and r['covered']]
        dev_area = sum(a for f,a,_ in results if f['spec']['role']=='pilot_dev')
        eval_area = sum(a for f,a,_ in results if f['spec']['role']=='pilot_eval')
        records.append(dict(policy=policy,branch=branch,budget=budget,cutoff=cutoff,
                            dev_area_deg2=dev_area,eval_area_deg2=eval_area,
                            evaluation_kind='archive_regression' if archive else ('fresh_frozen' if apply else 'development'),
                            target_dev_sky_groups=target,dev_sky_groups=count('pilot_dev'),
                            evaluation_sky_groups=count('pilot_eval'),
                            benchmark_n=len(valid),spatial_n=sum(r['spatial'] for r in valid),
                            correct_mode_n=sum(r['correct_mode_exists'] for r in valid),
                            blind_correct_n=sum(r['blind_correct'] for r in valid)))
    write_csv(output/'sky_group_comparison.csv', records)
    write_csv(output/'sky_group_blocks.csv', blocks)
    write_csv(output/'sky_group_recovery.csv', recovery)
    write_csv(output/'sky_group_candidates.csv', candidates)
    write_json(output/'sky_group_policy.json',dict(branch=branch,scales=scales,thresholds=frozen,recipe=recipe,limits=limits))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', type=Path, default=Path('results/summary'))
    p.add_argument('--output', type=Path, default=Path('results/group_budget'))
    p.add_argument('--branch', choices=('near','main','far'), default='main')
    p.add_argument('--archive', action='store_true')
    p.add_argument('--apply', type=Path)
    p.add_argument('--expected-dev', nargs='+')
    p.add_argument('--require-channels', nargs='+')
    a = p.parse_args()
    evaluate(a.summary,a.output,a.branch,a.archive,a.apply,a.expected_dev,a.require_channels)
