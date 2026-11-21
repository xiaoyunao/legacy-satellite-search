"""Verify actual paired CCD trial receipts and report conditional 10/15 pc changes."""

import argparse
import os
from pathlib import Path

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_fifteen_pc import OUTPUT, read, verify_registration

STAGES = ('N_rendered', 'N_exposed', 'N_final', 'N_psf', 'N_used', 'N_cmd')


def accept(label):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Verify native trial data on an allocated CPU')
    registration = verify_registration()
    tasks = read_csv(OUTPUT / 'tasks.csv')
    if len(tasks) != registration['native_cases']:
        raise ValueError('Native task inventory changed')
    tasks = tasks[:2] if label == 'pilot' else tasks
    counts = {r['parent_trial']: int(r['common_stamp_N_rendered'])
              for r in read_csv(OUTPUT / 'population_support.csv')}
    pairs, inputs = {}, {}
    for task in tasks:
        proof = OUTPUT / 'trials' / f"{task['site']}-{int(task['trial']):02d}.json"
        observed = read(proof)
        files = observed['outputs_from_native_sha256']
        if len(files) != 6 or any(sha(Path(p)) != h for p, h in files.items()):
            raise ValueError('Incomplete or changed native catalogue or geometry')
        inputs[str(proof)] = sha(proof)
        if {r['arm'] for r in observed['rows']} != {'baseline', 'deeper'} or len(observed['rows']) != 2:
            raise ValueError('Require exactly both formal A photometric arms')
        for row in observed['rows']:
            if any(row[k] != task[k] for k in task):
                raise ValueError('Measured row does not belong to the registered task')
            n = [int(row[k]) for k in STAGES]
            if n[0] != counts[row['parent_trial']] or n != sorted(n, reverse=True) or not 0 <= int(row['N_initial']) <= n[1]:
                raise ValueError('Native source counts violate the stage or common-population definition')
            key = (row['site'], row['parent_trial'], row['arm'])
            pairs.setdefault(key, {})[int(row['rh_pc'])] = row
    report = []
    for (site, parent, arm), radii in sorted(pairs.items()):
        if set(radii) != {10, 15}:
            raise ValueError('Each population and sky requires both radius cases')
        record = dict(site=site, original_trial=parent, arm=arm)
        for r, row in sorted(radii.items()):
            for key in (*STAGES, 'N_initial', 'spatial', 'blind_correct', 'correct_mode_exists',
                        'blind_dm_error', 'offset_arcmin'):
                record[f'r{r}_{key}'] = row.get(key)
        for key in (*STAGES, 'N_initial'):
            record[f'delta_{key}'] = radii[15][key] - radii[10][key]
        report.append(record)
    output = OUTPUT / f'{label}_pairs.csv'
    write_csv(output, report)
    write_json(OUTPUT / f'{label}_acceptance.json', dict(job=os.environ['SLURM_JOB_ID'],
        native_cases=len(tasks), measured_pairs=len(report), skies=len({r['site'] for r in report}),
        latent_populations=len({r['original_trial'] for r in report}), inputs=inputs, table_sha256=sha(output),
        code_sha256=sha(Path(__file__)), every_input_verified=True,
        scope='Finite common-stamp populations, paired across 10 and 15 pc. Catalogued sources, native detections, original formal A limits and whole-field blind recovery are measured. A pilot covers one population on one background. No complete physical luminosity response, cross-survey sensitivity or abundance inference.'))
    print(dict(label=label, native_cases=len(tasks), measured_pairs=len(report)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('label', choices=('pilot', 'full'))
    accept(p.parse_args().label)
