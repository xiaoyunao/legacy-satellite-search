"""Submit or resume frozen residual fields from their manifest status."""
import argparse
import json
from pathlib import Path
import subprocess

import yaml

from ls_satsearch.run import write_json


BATCH = 8
JOBS = Path('logs/v14-dispatch.json')


def submit(options):
    command = ['sbatch', '--parsable', '-A', 'desi', '-q', 'regular', '-C', 'cpu',
               '-N1', '-n8', '-c4', '--mem=104G', '-t', '01:20:00', '-o', 'logs/%x-%A_%a.log']
    return subprocess.check_output(command + options, text=True).strip().split(';')[0]


def missing(fields, cohort):
    for i, field in enumerate(fields):
        manifest = Path(f'regional_v14_{cohort}/results/summary/{field["id"]}-base/manifest.json')
        if (not manifest.exists()
            or json.loads(manifest.read_text()).get('status') not in ('complete', 'no_usable_gr')):
            yield i // BATCH


def run(cohorts, depends, limit, resume):
    jobs = json.loads(JOBS.read_text()) if JOBS.exists() else {}
    for cohort in cohorts:
        path = Path(f'configs/v14/cohorts/{cohort}/fields.yaml')
        fields = yaml.safe_load(path.read_text())['fields']
        if not fields:
            continue
        chunks = sorted(set(missing(fields, cohort)))
        if not chunks:
            continue
        if jobs.get(cohort):
            if not resume:
                continue
            with_queue = subprocess.check_output(['squeue', '-h', '-j', ','.join(x['job'] for x in jobs[cohort])],
                                                 text=True, stderr=subprocess.DEVNULL)
            if with_queue.strip():
                raise ValueError(f'{cohort} still has active jobs')
        dep = ['--dependency=afterok:' + depends, '--kill-on-invalid-dep=yes'] if depends else []
        array = ','.join(map(str, chunks)) if resume else f'{chunks[0]}-{chunks[-1]}'
        job = submit([f'--array={array}%{limit}', '-J', 'ls14-'+cohort, *dep,
                      'scripts/v14_batches.sh', cohort, str(len(fields))])
        jobs.setdefault(cohort, []).append(dict(job=job, fields=len(fields), tasks=len(chunks), array=array))
        write_json(JOBS, jobs)
        print(cohort, job, len(fields), len(chunks), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cohorts', nargs='+')
    p.add_argument('--depends')
    p.add_argument('--limit', type=int, default=3)
    p.add_argument('--resume', action='store_true')
    run(**vars(p.parse_args()))
