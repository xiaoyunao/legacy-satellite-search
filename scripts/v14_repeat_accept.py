"""Accept the complete registered initial CCD tranche using aggregate evidence.

This gate reads no source catalogues. Partial measurement success alone cannot
certify all three backgrounds, all nine trials and both LS selection arms.
"""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path

import yaml


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def validate_rows(rows, expected):
    keys = [(r['site'], int(r['trial']), r['arm']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Initial tranche is missing, duplicating or adding a trial/arm')
    for row in rows:
        values = [int(row[k]) for k in
                  ('N_imf', 'N_rendered', 'N_exposed', 'N_final', 'N_psf', 'N_used')]
        if values[-1] < 0 or any(a < b for a, b in zip(values, values[1:])):
            raise ValueError('Native detection/selection denominators are inconsistent')
        if row.get('shared_population_rows_verified') != 'True':
            raise ValueError('Shared native/PS1 population-row verification is absent')


def run(root, full=False):
    config = root/'configs/v14_repeat'
    initial = root/'results/v14/repeat'
    output = root/('results/v14/repeat_full' if full else 'results/v14/repeat')
    registration = initial/'registration.json'
    saved = json.loads(registration.read_text())
    protocol_path = config/'protocol.yaml'
    plan_path = config/'image_trials.yaml'
    if (saved['protocol_sha256'] != digest(protocol_path) or
            saved['plan_sha256'] != digest(plan_path)):
        raise ValueError('Registered physical protocol changed')
    protocol = yaml.safe_load(protocol_path.read_text())
    plan = yaml.safe_load(plan_path.read_text())
    sites = [r['field'] for r in read(config/'image_fields.csv')]
    if len(sites) != len(set(sites)) or set(sites) != set(saved['blank_sha256']):
        raise ValueError('Registered backgrounds changed')
    trials = list(range(len(plan['conditions']))) if full else protocol['initial_trial_indices']
    arms = ('ls_base', 'ls_deep')
    expected = {(s, t, a) for s in sites for t in trials for a in arms}
    rows, sources = [], {str(p.relative_to(root)): digest(p) for p in
                         (registration, protocol_path, plan_path, config/'image_fields.csv')}
    stage_count = 0
    for site in sites:
        prefix = root/('results/v14_repeat_full/image_response' if full else 'results/v14_repeat/image_response')/site
        paths = [prefix.with_suffix('.json'), Path(str(prefix)+'-blind.csv'),
                 Path(str(prefix)+'-stages.csv')]
        metadata = json.loads(paths[0].read_text())
        if metadata['blank_sha256'] != saved['blank_sha256'][site]:
            raise ValueError('Measurement background differs from registered native blank')
        if metadata['plan_sha256'] != saved['plan_sha256'] or metadata['measured_trials'] != len(trials):
            raise ValueError('Partial or stale site measurement: '+site)
        part = read(paths[1]); rows.extend(part)
        stages = read(paths[2]); stage_count += len(stages)
        stage_keys = [(int(r['trial']), r['arm'], r['g_lo'], r['g_hi'], r['environment']) for r in stages]
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError('Duplicate stage-count bins: '+site)
        for t in trials:
            proof = initial/'validation'/f'{site}-trial{t:02d}.json'
            native = json.loads(proof.read_text())
            if not native['native_products_validated']:
                raise ValueError('Native product validation failed')
            for arm in arms:
                matches = [r for r in metadata['inputs'] if int(r['trial']) == t and r['arm'] == arm]
                if len(matches) != 1 or matches[0]['tractor_sha256'] != native['tractor_sha256']:
                    raise ValueError('Measurement does not use the validated native catalogue')
                if full and matches[0].get('truth_sha256')!=native['truth_sha256']:
                    raise ValueError('Measurement does not use the validated latent population')
                totals = [r for r in stages if int(r['trial']) == t and r['arm'] == arm
                          and float(r['g_lo']) == -10 and float(r['g_hi']) == 30
                          and r['environment'] == 'all']
                record = next(r for r in part if int(r['trial']) == t and r['arm'] == arm)
                if len(totals) != 1 or any(int(totals[0][k]) != int(record[v]) for k, v in
                                         [('exposed','N_exposed'), ('detected','N_final'),
                                          ('psf','N_psf'), ('selected','N_used')]):
                    raise ValueError('Stage counts and blind measurement disagree')
                for key, value in zip(('D_kpc','rh_pc','expected_MV_proxy'), plan['conditions'][t]):
                    if not math.isclose(float(record[key]), float(value), abs_tol=1e-12):
                        raise ValueError('Measured physical cell differs from registration')
            sources[str(proof.relative_to(root))] = digest(proof)
        for path in paths:
            sources[str(path.relative_to(root))] = digest(path)
    validate_rows(rows, expected)
    if full:
        for row in rows:
            if not 0 <= int(row['N_cmd_at_truth_dm']) <= int(row['N_used']):
                raise ValueError('CMD diagnostic denominator is inconsistent')
            if int(row['latent_population_id']) != int(row['trial']) or int(row['realization_id']) != int(row['trial'])//6:
                raise ValueError('Shared population identifiers are inconsistent')
    for trial in trials:
        part = [r for r in rows if int(r['trial']) == trial]
        shared = ('N_imf','N_rendered','realized_MV_proxy','seed','model_sha256',
                  'ps1_model_sha256','source_poisson_seed')
        if len({tuple(r[k] for k in shared) for r in part}) != 1:
            raise ValueError('Latent physical population differs between backgrounds/arms')
        for site in sites:
            site_rows = [r for r in part if r['site'] == site]
            if len({tuple(r[k] for k in ('N_exposed','N_final','N_psf')) for r in site_rows}) != 1:
                raise ValueError('Same native detections differ between selection arms')
    summary = output/('full_summary.csv' if full else 'initial_nine_summary.csv')
    columns = ['site','trial','arm','D_kpc','rh_pc','expected_MV_proxy','realized_MV_proxy',
               'N_imf','N_rendered','N_exposed','N_final','N_psf','N_used','blank_spatial',
               'spatial','correct_mode_exists','blind_correct','blind_dm','blind_dm_error',
               'c_modes_fit','c_ts','c_after_top3']
    if full:columns += ['latent_population_id','realization_id','N_cmd_at_truth_dm']
    with summary.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:r.get(k, '') for k in columns} for r in rows)
    report = dict(utc=datetime.now(timezone.utc).isoformat(), job=os.getenv('SLURM_JOB_ID'),
                  backgrounds=len(sites), native_trials=len(expected)//len(arms),
                  arm_measurements=len(rows), stage_rows=stage_count,
                  **{('all_native_and_LS_measurements_accepted' if full else 'all_initial_trials_accepted'):True},
                  summary_sha256=digest(summary),
                  source_sha256=sources, code_sha256=digest(Path(__file__)),
                  scope=('All frozen native and LS-arm measurements accepted. Shared population IDs remain dependent across backgrounds. Physical PS1 response validation, finite-stamp recovery sensitivity and gain uncertainty remain separate acceptance requirements; this gate does not certify them.' if full else
                  'Initial software/resource/data-integrity tranche only. One population draw per bright-radius cell is shared across three fixed backgrounds; these are not nine independent populations. No interim significance test, PS1 physical gain, full 144-trial completion or population completeness is claimed.'))
    (output/('full_acceptance.json' if full else 'initial_nine_acceptance.json')).write_text(json.dumps(report, indent=2)+'\n')
    print({k:report[k] for k in ('backgrounds','native_trials','arm_measurements','stage_rows')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--full', action='store_true')
    args=parser.parse_args()
    run(args.root.resolve(),full=args.full)
