"""Run registered single-field retries as four local workers in one Slurm step."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from queue import Queue
import socket
import subprocess

from ls_satsearch.run import read_csv, sha, write_json


def run(path,index):
    home=Path.cwd();data=Path(os.environ['PSCRATCH'])/'legacy-satellite-search'
    if not (os.environ.get('SLURM_JOB_ID') and os.environ.get('SLURM_STEP_ID','').isdigit()
            and socket.gethostname().startswith('nid')):
        raise ValueError('Use one allocated16CPU compute step, never a login node')
    registry=json.loads(Path('logs/v14-retry-jobs.json').read_text())
    parent=os.environ.get('SLURM_ARRAY_JOB_ID',os.environ['SLURM_JOB_ID'])
    if parent not in registry or registry[parent]['sha256']!=sha(path):
        raise ValueError('Unregistered or changed packed retry worklist')
    tasks=[r for r in read_csv(path) if int(r['array_task_index'])==index]
    if not tasks:raise ValueError('No registered retry fields for this task')
    cpus=sorted(os.sched_getaffinity(0))
    if len(cpus)<16:raise ValueError('Packed retry needs16 allocated CPUs')
    slots=Queue()
    for start in range(0,16,4):slots.put(cpus[start:start+4])

    def execute(row):
        cohort,field=row['cohort'],row['field'];workspace=home/f'regional_v14_{cohort}'
        manifest=workspace/f'results/summary/{field}-base/manifest.json'
        if manifest.is_file() and json.loads(manifest.read_text()).get('status') in ('complete','no_usable_gr'):
            return dict(field=field,state='existing_terminal_manifest_preserved')
        assigned=slots.get()
        env=dict(os.environ,LS_SAT_VERSION='v14',LS_SAT_SKIP_EMPTY='1',LS_SAT_WORKSPACE=str(home),
            LS_SAT_PROFILE='cohorts/'+cohort,LS_SAT_V2_WORKSPACE='1',SLURM_CPUS_PER_TASK='4')
        if (home/'results/v14/footprint/coadd_cache_validation.json').is_file():
            env['LS_SAT_COADD_CACHE']=str(data/'cache/v14_packed_masks')
        env.pop('SLURM_TRES_PER_TASK',None)
        log=home/'logs'/f'packed-retry-{parent}-{field}.log'
        print('PACKED_RETRY_START',field,flush=True)
        try:
            with log.open('w') as stream:
                result=subprocess.run(['taskset','-c',','.join(map(str,assigned)),
                    'bash',str(home/'scripts/v6.sh'),'run',field],cwd=workspace,
                    env=env,stdout=stream,stderr=subprocess.STDOUT)
        finally:slots.put(assigned)
        state=json.loads(manifest.read_text()).get('status') if manifest.is_file() else 'missing'
        passed=result.returncode==0 and state in ('complete','no_usable_gr')
        print('PACKED_RETRY_END',field,passed,state,flush=True)
        return dict(field=field,state=state,exit_code=result.returncode,passed=passed)

    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(execute,tasks))
    out=path.parent/f'packed-task-{index:03d}.json'
    write_json(out,dict(job=os.environ['SLURM_JOB_ID'],worklist_sha256=sha(path),
        node=socket.gethostname(),results=results,code_sha256=sha(Path(__file__))))
    if any(r.get('passed') is False for r in results):raise SystemExit('Failed fields retained for manifest-based retry')


def finish(path):
    saved=json.loads(path.with_name('execution.json').read_text())
    if saved['worklist_sha256']!=sha(path):raise ValueError('Packed retry map changed')
    passed=True;per_job={}
    for row in read_csv(path):
        p=Path(f"regional_v14_{row['cohort']}/results/summary/{row['field']}-base/manifest.json")
        if not p.is_file():
            passed=False;per_job[row['original_job']]=False;continue
        m=json.loads(p.read_text());terminal=m.get('status') in ('complete','no_usable_gr')
        terminal &= m['field']['id']==row['field'] and m['fields_sha256']==sha(Path(f"configs/v14/cohorts/{row['cohort']}/fields.yaml"))
        if m.get('status')=='complete':
            data=Path(os.environ['PSCRATCH'])/'legacy-satellite-search'
            terminal &= p.with_name('deduplicated_peaks.csv').is_file() and (data/m['owned_coverage_path']).is_file()
        passed &= terminal
        per_job[row['original_job']]=terminal
    changes=[]
    for job in saved['original_pending_holds']:
        info=subprocess.run(['scontrol','show','job','-o',job],text=True,capture_output=True)
        if 'JobState=PENDING' not in info.stdout or 'Reason=JobHeldUser' not in info.stdout:
            changes.append(dict(job=job,action='not_our_pending_hold_preserved'));continue
        accepted=per_job.get(job,False)
        command=['scancel','--state=PENDING',job] if accepted else ['scontrol','release',job]
        subprocess.run(command,check=True)
        changes.append(dict(job=job,action='superseded_after_real_terminal_manifests' if accepted else 'original_fallback_released'))
    saved.update(state='packed_fields_accepted' if passed else 'partial_products_preserved_original_fallback_released',
        guard_job=os.environ.get('SLURM_JOB_ID'),guard_actions=changes)
    write_json(path.with_name('execution.json'),saved)
    print(saved['state'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('run','finish'))
    p.add_argument('worklist',type=Path);p.add_argument('index',type=int,nargs='?')
    args=p.parse_args();finish(args.worklist) if args.mode=='finish' else run(args.worklist,args.index)
