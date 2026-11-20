"""Pilot, then complete the fixed deeper arm on the existing144 catalogues."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

from ls_satsearch.run import sha,write_json

ROOT=Path('results/v14/repeat_full/production_deeper_replay')
SITES=[f'v14_south_response_{i}' for i in (1,2,3)]


def run(full=False):
    if not os.getenv('SLURM_JOB_ID') or not os.getenv('SLURM_STEP_ID','').isdigit():
        raise RuntimeError('Allocate one CPU step with24CPUs')
    cpus=sorted(os.sched_getaffinity(0))
    if len(cpus)<24:raise ValueError('Need three disjoint eight-CPU workers')
    subprocess.run(['.venv/bin/python','-u','-m','scripts.v14_production_deeper_replay','prepare'],check=True)
    registration_sha=sha(ROOT/'registration.json')
    if full:
        proof=json.loads((ROOT/'pilot_acceptance.json').read_text())
        if not proof['accepted'] or proof['registration_sha256']!=registration_sha:
            raise ValueError('Accept the registered18-case pilot first')
    def execute(item):
        index,site=item;env=dict(os.environ,SLURM_CPUS_PER_TASK='8')
        env.pop('SLURM_TRES_PER_TASK',None)
        command=['taskset','-c',','.join(map(str,cpus[index*8:(index+1)*8])),'.venv/bin/python',
            '-u','-m','scripts.v14_production_deeper_replay','run','--field',site]
        if not full:command+=['--trials',*[str(i) for i in range(6)]]
        with (Path('logs')/f'{os.environ["SLURM_JOB_ID"]}-deeper-{site}.log').open('w') as stream:
            result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
        return dict(site=site,exit_code=result.returncode)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(execute,enumerate(SITES)))
    write_json(ROOT/('full_batch_status.json' if full else 'pilot_batch_status.json'),
        dict(job=os.environ['SLURM_JOB_ID'],results=results))
    if any(r['exit_code'] for r in results):raise RuntimeError('Preserve caches; inspect actual failed worker')
    expected=list(range(48 if full else 6))
    for site in SITES:
        meta=json.loads((ROOT/(site+'.json')).read_text())
        if meta['requested_trials']!=expected or meta['rows']!=len(expected):
            raise ValueError('Incomplete registered trial subset')
    if sha(ROOT/'registration.json')!=registration_sha:raise ValueError('Registration changed')
    write_json(ROOT/('completion.json' if full else 'pilot_completion.json'),
        dict(job=os.environ['SLURM_JOB_ID'],registration_sha256=registration_sha,
            native_catalogue_replays=len(expected)*3,backgrounds=3,full144=full,
            source_sha256={str(p):sha(p) for site in SITES for p in (ROOT/(site+'.csv'),ROOT/(site+'.json'))},
            runner_sha256=sha(Path(__file__)),C_replayed=False,physical_PS1_response_validated=False,
            scope='Fixed deeper research policy on the same registered native populations. Pure A-detection response; no new extraction, population, discovery area, borrowed C or global completeness. Pilot completion requires independent result/source QA before full execution.'))
    print('DEEPER_REPLAY_BATCH_COMPLETE',len(expected)*3,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--full',action='store_true')
    run(parser.parse_args().full)
