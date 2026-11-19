"""Run three already registered production-policy replays in one CPU step."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from ls_satsearch.run import sha, write_json


def run():
    root = Path('results/v14/repeat_full/production_replay')
    if not os.getenv('SLURM_JOB_ID') or not os.getenv('SLURM_STEP_ID', '').isdigit():
        raise ValueError('Use an allocated Slurm CPU step')
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) < 24:
        raise ValueError('Allocate 24 CPUs for three disjoint eight-CPU workers')
    sites = [f'v14_south_response_{i}' for i in (1, 2, 3)]
    registration = root/'registration.json'
    registered_sha = sha(registration)
    for site in sites:
        pilot = json.loads((root/(site+'.json')).read_text())
        if pilot['requested_trials'] != list(range(6)) or pilot['rows'] != 6:
            raise ValueError('Complete the first-six check in every background first')
    def execute(item):
        index, site = item
        env = dict(os.environ, SLURM_CPUS_PER_TASK='8')
        env.pop('SLURM_TRES_PER_TASK', None)
        with (Path('logs')/f'{os.environ["SLURM_JOB_ID"]}-production-full-{site}.log').open('w') as stream:
            result = subprocess.run(['taskset', '-c', ','.join(map(str, cpus[index*8:(index+1)*8])),
                '.venv/bin/python', '-u', '-m', 'scripts.v14_production_replay',
                'run', '--field', site], env=env, stdout=stream, stderr=subprocess.STDOUT)
        return dict(site=site, exit_code=result.returncode)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(execute, enumerate(sites)))
    write_json(root/'batch_status.json', dict(job=os.environ['SLURM_JOB_ID'], results=results,
        utc=datetime.now(timezone.utc).isoformat()))
    if any(row['exit_code'] for row in results):
        raise RuntimeError('A replay failed; preserve caches and retry only incomplete sites')
    for site in sites:
        meta = json.loads((root/(site+'.json')).read_text())
        if not meta['complete_registered_site'] or meta['rows'] != 48:
            raise ValueError('Incomplete registered site')
    if sha(registration) != registered_sha:
        raise ValueError('Registration changed during execution')
    write_json(root/'completion.json', dict(job=os.environ['SLURM_JOB_ID'],
        native_catalogue_replays=144, backgrounds=3, all_registered_baseline_replays_complete=True,
        registration_sha256=registered_sha,
        source_sha256={str(p):sha(p) for site in sites for p in (root/(site+'.csv'), root/(site+'.json'))},
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        C_replayed=False, physical_PS1_response_validated=False,
        scope='Production baseline on three existing control skies; no new CCD populations, candidate area, borrowed C fits or all-sky completeness.'))
    print('ALL144_PRODUCTION_BASELINE_REPLAYS_COMPLETE', flush=True)


if __name__ == '__main__':
    run()
