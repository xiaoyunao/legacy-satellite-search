"""Submit only checksum-manifest-ready PS1 fields from a NERSC login node."""

import argparse
import fcntl
import json
import os
from pathlib import Path
from subprocess import check_output

import yaml

from ls_satsearch.run import write_json


def submit(workspace, region, field, kind):
    common=['sbatch','--parsable','-A','desi','-q','regular','-C','cpu','-N1','-n1','-c4']
    profile=f'LS_SAT_WORKSPACE={workspace},LS_SAT_VERSION=v12,LS_SAT_PROFILE=matched/{region}'
    name=f'ls12-{kind}-{field}'
    opts=['-J',name,'-o','logs/%x-%j.log','--export=ALL,'+profile]
    if kind=='match':
        cmd=['--mem=12G','-t','00:35:00','scripts/v12_matched.sh',region,field]
    elif kind=='selection':
        policy=f'results/v12/matched/{region}'
        archive=f'matched_v12_{region}/results/matched'
        cmd=['--mem=12G','-t','02:00:00','--wrap',
             f'bash scripts/v6.sh response_trials {field} --version v12 --archive {archive} '
             f'--policy-archive {policy} --physical-plan configs/v12/physical_trials.yaml '
             f'--output results/v12/selection_trials/{region}']
    else:
        cmd=['--mem=10G','-t','00:35:00','--wrap',
             f'export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11 '
             f'LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" '
             f'LS_SAT_CONFIG_DIR="$PWD/configs/v12/matched/{region}" PYTHONPATH=src OPENBLAS_NUM_THREADS=1; '
             f'.venv/bin/python -u scripts/v12_matched_results.py {region} results/v12/matched/{region}']
    job=check_output(common+opts+cmd,text=True).strip().split(';')[0]
    print(region,kind,field,job,flush=True)
    return job


def dispatch(region, retry):
    workspace=str(Path.cwd())
    base=Path(f'matched_v12_{region}/results/matched')
    modes=Path(f'configs/v12/matched/{region}/matched.yaml')
    resources=Path(os.environ['PSCRATCH'])/'legacy-satellite-search/resources/ps1/tiles-v3'
    fields=yaml.safe_load(modes.read_text())['fields']
    state=Path(f'logs/ls12-ps1-submit-{region}.json')
    with state.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        saved=json.loads(state.read_text()) if state.exists() else {}
        for key in retry:
            if key not in saved:
                raise ValueError(f'No submitted job {key}')
            job=saved[key]
            status=check_output(['sacct','-X','-j',job,'-n','-o','State'],text=True).strip()
            if status not in ('FAILED','OUT_OF_MEMORY','TIMEOUT','CANCELLED','NODE_FAIL'):
                raise ValueError(f'{job}: expected terminal failure, saw {status}')
            del saved[key]
            write_json(state,saved)
        for spec in fields:
            field=spec['id']
            key=f'match/{field}'
            if key not in saved and (resources/field/'manifest.json').exists():
                saved[key]=submit(workspace,region,field,'match')
                write_json(state,saved)

        needed=[spec['id'] for spec in fields if spec['role']=='pilot_dev']
        def complete(field):
            paths=[base/s/'summary'/f'{field}-base'/'manifest.json' for s in ('ls_base','ls_deep','ps1')]
            return all(p.is_file() and json.loads(p.read_text())['status']=='complete' for p in paths)

        policy=Path(f'results/v12/matched/{region}/common_mask_comparison.csv')
        if all(complete(f) for f in needed) and 'calibrate' not in saved:
            saved['calibrate']=submit(workspace,region,region,'calibrate')
            write_json(state,saved)
        if policy.is_file():
            for field in needed:
                key=f'selection/{field}'
                if key not in saved:
                    saved[key]=submit(workspace,region,field,'selection')
                    write_json(state,saved)
        def covered_or_unusable(field):
            path=base/'coverage'/f'{field}.json'
            return complete(field) or (path.is_file() and json.loads(path.read_text())['status']=='no_joint_area')

        if policy.is_file() and all(covered_or_unusable(f['id']) for f in fields) and 'final_compare' not in saved:
            saved['final_compare']=submit(workspace,region,region,'calibrate')
            write_json(state,saved)
        print(region,len([k for k in saved if k.startswith('match/')]),'of',len(fields),'matched submitted',
              sum(complete(f['id']) for f in fields),'matched complete',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('region',choices=('north','south'))
    p.add_argument('--retry',action='append',default=[])
    a=p.parse_args()
    dispatch(a.region,a.retry)
