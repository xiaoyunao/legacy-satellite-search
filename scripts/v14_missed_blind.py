"""Compare A depth arms for four known misses at a local matched group budget."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

import numpy as np

from ls_satsearch.data import select
from ls_satsearch.group_budget import cut, groups, matches
from ls_satsearch.run import coverage_metrics, field_cache, read_csv, sha, write_csv, write_json
from ls_satsearch.search import deduplicate, load_isochrone, scan
from scripts.v14_missed_controls import MASK, OUT
from scripts.v14_production_benchmarks import separation

BENCHMARKS = Path('references/benchmarks.csv')
CONTROL_COUNT = 6
REVIEW_BUDGET = .3


def register(output):
    receipt = MASK / 'post_outside_C_registration_20261120.json'
    link = json.loads(receipt.read_text())
    path = Path(link['registration'])
    if sha(path) != link['registration_sha256']:
        raise ValueError('Production registration changed')
    production = json.loads(path.read_text())
    fixed = OUT / 'missed_controls_fixed_diagnostics.csv'
    target = {r['name']: r['field'] for r in read_csv(fixed)}
    truths = read_csv(BENCHMARKS)
    qualified = {r['field']: r for r in production['records']
                 if r['classification'] == 'qualified_discovery' and r['region'] == 'south'
                 and r['apply_ownership'] is None and r['source_effective_deg2'] > 0}
    plans = []
    for name, field in sorted(target.items()):
        original = qualified[field]
        ra, dec, width, *_ = original['geometry']
        options = []
        for row in qualified.values():
            if row['workspace'] != original['workspace'] or row['field'] in target.values():
                continue
            x, y, w, *_ = row['geometry']
            distance = separation(ra, dec, x, y)
            if distance < 45 * (width + w):
                continue
            if not .65 <= row['source_effective_deg2'] / original['source_effective_deg2'] <= 1.5:
                continue
            if any(separation(x, y, float(t['ra_deg']), float(t['dec_deg'])) < 45 * w for t in truths):
                continue
            options.append((distance, row['field'], row))
        controls = [row for _, _, row in sorted(options)[:CONTROL_COUNT]]
        if len(controls) != CONTROL_COUNT:
            raise ValueError(f'Insufficient same-workspace controls for {name}')
        plans.append(dict(target=name, test=original, controls=controls))
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'registration.json', dict(
        input_sha256={str(f): sha(f) for f in (receipt, path, fixed, BENCHMARKS)},
        job=os.environ['SLURM_JOB_ID'], code_sha256=sha(Path(__file__)), tests=plans,
        budget=REVIEW_BUDGET, deeper_mag=.5,
        control_rule='Nearest owned fields in the same regional workspace. Geometry and represented area only. Known benchmark positions and test fields excluded.'))


def grouped(records, arm):
    return groups([dict(row, channel=arm, ranking=row['score']) for row in records])


def measure(task):
    data_path = Path(os.environ['LS_SAT_DATA'])
    dr11_root = Path(os.environ['LS_DR11_ROOT'])
    manifest_path = Path(task['manifest'])
    if sha(manifest_path) != task['manifest_sha256']:
        raise ValueError('Original field manifest changed')
    saved = json.loads(manifest_path.read_text())
    config = saved['config']
    template = data_path / 'resources' / config['isochrone']
    if sha(template) != saved['model_sha256'] or config['methods'] != ['A']:
        raise ValueError('Require the frozen A-only observation and model')
    if task['raster'] != saved['owned_coverage_path']:
        raise ValueError('Require original stored owned coverage')
    owned_path = data_path / task['raster']
    area_owned = np.load(owned_path, mmap_mode='r', allow_pickle=False)
    field, raw, area, _ = field_cache(dr11_root, data_path, saved['field'], config, None)
    area_deg2, _ = coverage_metrics(field, area_owned, config)
    if not np.isclose(area_deg2, task['source_effective_deg2'], atol=1e-9, rtol=0):
        raise ValueError('Owned mask differs from the accepted area')
    base_path = data_path / saved['deduplicated_peaks_path']
    base = [{key: float(row[key]) for key in ('x', 'y', 'ra_deg', 'dec_deg', 'dm', 'rh_arcmin', 'score')}
            for row in read_csv(base_path) if row['branch'] == 'main']
    deeper = dict(config, g_max=config['g_max'] + .5, r_max=config['r_max'] + .5, dm=[16.5, 20.75, .25])
    sources, *_ = select(raw, field, area, deeper)
    peaks, _, _, _ = scan(sources, field, area, load_isochrone(template), deeper)
    cell = field.step / config['coverage_subdivision']
    # Use the stored owned WCS cells for peak centres and the full usable mask
    # for on/off counting, as in the original buffered search.
    owned = [row for row in peaks
             if area_owned[int((row['y'] + field.limit) / cell), int((row['x'] + field.limit) / cell)]]
    result = {'base': grouped(base, 'A_base'), 'deep': grouped(deduplicate(owned), 'A_deep')}
    proof = dict(field=task['field'], area=area_deg2, template_sha256=sha(template),
                 owned_sha256=sha(owned_path), original_baseline_peaks_sha256=sha(base_path),
                 original_manifest_sha256=task['manifest_sha256'],
                 groups_base=len(result['base']), groups_deep=len(result['deep']))
    return task['field'], result, proof, config


def report(output, index):
    path = output / 'registration.json'
    registration = json.loads(path.read_text())
    if registration['code_sha256'] != sha(Path(__file__)):
        raise ValueError('Registered replay code changed')
    for name, digest in registration['input_sha256'].items():
        if sha(Path(name)) != digest:
            raise ValueError(f'Registered input changed: {name}')
    plan = registration['tests'][index]
    tasks = [plan['test'], *plan['controls']]
    with ProcessPoolExecutor(max_workers=int(os.environ['SLURM_CPUS_PER_TASK'])) as pool:
        receipts = list(pool.map(measure, tasks))
    _, target_groups, target_proof, cfg = receipts[0]
    controls = receipts[1:]
    calibration_area = sum(row[2]['area'] for row in controls)
    truth = next(r for r in read_csv(BENCHMARKS) if r['name'] == plan['target'])
    rows = []
    for arm in ('base', 'deep'):
        scores = [anchor['ranking'] for _, grouped_controls, _, _ in controls
                  for anchor, _ in grouped_controls[arm]]
        threshold, intended_count = cut(scores, calibration_area, REVIEW_BUDGET)
        if threshold is None:
            raise ValueError('The control scan produced no usable budget cutoff')
        rows.append(dict(target=plan['target'], search_field=target_proof['field'], arm=arm, threshold=threshold,
                         target_area_deg2=target_proof['area'], calibration_area_deg2=calibration_area,
                         expected_control_groups=intended_count, actual_control_groups=sum(s >= threshold for s in scores),
                         target_field_groups=sum(a['ranking'] >= threshold for a, _ in target_groups[arm]),
                         **matches(target_groups[arm], truth, threshold, cfg)))
    target_output = output / plan['target']
    target_output.mkdir()
    table = target_output / 'paired_blind.csv'
    write_csv(table, rows)
    write_json(target_output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], source_sha256=sha(path),
        table_sha256=sha(table), measured=[row[2] for row in receipts],
        scope='Local retrospective A test with unchanged main distance grid, radii, candidate budget and parent catalogue. Baseline peaks are historical. New deeper peaks and calibration use original working-area cells. Matching applies the fixed position rule only after calibration. This does not replace production thresholds or estimate completeness.'))
    print(rows, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use an allocated compute job')
    if args.index is None:
        register(args.output)
    else:
        report(args.output, args.index)
