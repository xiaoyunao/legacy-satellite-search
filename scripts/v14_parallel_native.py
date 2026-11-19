"""Transfer only pending registered CCD tasks to one owned CPU allocation, with fallback."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
import re
from queue import Queue
import shutil
import socket
from pathlib import Path
import subprocess

from ls_satsearch.run import read_csv,sha,write_json

STATE=Path('results/v14/repeat_full/parallel_handoff.json')
ARRAY='61568439'
MEASURE='61568456'


def queue():
    output=subprocess.check_output(['squeue','--array','-h','-j',ARRAY,'-o','%i|%T|%R'],text=True)
    return [line.split('|',2) for line in output.splitlines()]


def complete_grid():
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    import yaml
    conditions=yaml.safe_load(Path('configs/v14_repeat/image_trials.yaml').read_text())['conditions']
    missing=[]
    for site in sites:
        for t in range(len(conditions)):
            p=Path('results/v14/repeat/validation')/(site['field']+f'-trial{t:02d}.json')
            if not p.is_file() or not json.loads(p.read_text()).get('native_products_validated'):missing.append(str(p))
    return missing


def install(job):
    if STATE.exists():
        previous=json.loads(STATE.read_text())
        if previous['state']!='partial_owned_products_preserved_original_queue_released':
            raise ValueError('An owned handoff is already registered')
        archive=STATE.with_name('parallel_handoff_'+previous['owned_job']+'.json')
        if archive.exists() and sha(archive)!=sha(STATE):raise ValueError('Prior handoff archive changed')
        if not archive.exists():shutil.copy2(STATE,archive)
    current=queue()
    if any(reason=='(JobHeldUser)' or 'JobHeldUser' in reason for _,_,reason in current):
        raise ValueError('Original array has an unrelated existing hold')
    info=subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    allocated=int(re.search(r'\bNumCPUs=(\d+)',info)[1])
    if not ('JobState=RUNNING' in info and 'Account=desi' in info and allocated>=32):
        raise ValueError('Owned 32CPU allocation not verified')
    spec=Path('configs/v14_repeat/remaining_tasks.csv')
    record=dict(utc=datetime.now(timezone.utc).isoformat(),owned_job=job,original_array=ARRAY,
        final_measurement=MEASURE,worklist=str(spec),worklist_sha256=sha(spec),state='prepared',tasks=[],
        workers=4,cpus_per_worker=8,memory_policy='One64GiB step shared by four workers; observed native peaks below7GiB/task',allocated_cpus=allocated,
        allocation_slurm_readback=info.strip())
    write_json(STATE,record)
    guard=subprocess.check_output(['sbatch','--parsable','-A','desi','-C','cpu','-q','debug','-N1','-n1','-c1',
        '--mem=4G','-t','00:10:00','--dependency=afterany:'+job,'-J','ls14-native-handoff-finish','-o','logs/%x-%j.log',
        '--wrap','export PYTHONPATH=src:.; exec .venv/bin/python -u -m scripts.v14_parallel_native finish'],text=True).strip().split(';')[0]
    record['guard_job']=guard;write_json(STATE,record)
    held=subprocess.run(['scontrol','hold',ARRAY],capture_output=True,text=True)
    actual=queue()
    targets=[]
    for identity,status,reason in actual:
        if status=='PENDING':
            if 'JobHeldUser' not in reason:raise ValueError('Pending task not actually held: '+identity)
            targets.append(int(identity.split('_')[1]))
    record.update(tasks=sorted(targets),state='pending_tasks_held_for_owned_execution',
        hold_command_returncode=held.returncode,hold_diagnostics=(held.stdout+held.stderr).strip(),
        original_running_tasks=[identity for identity,status,_ in actual if status!='PENDING'])
    write_json(STATE,record)
    print('REGISTERED_OWNED_NATIVE_HANDOFF',job,len(targets),guard,flush=True)


def run():
    record=json.loads(STATE.read_text());job=os.environ.get('SLURM_JOB_ID')
    if job!=record['owned_job']:raise ValueError('Not inside the registered owned allocation')
    if sha(Path(record['worklist']))!=record['worklist_sha256']:raise ValueError('Frozen native worklist changed')
    if not (os.environ.get('SLURM_STEP_ID','').isdigit() and socket.gethostname().startswith('nid')):
        raise ValueError('Run the driver inside one allocated32CPU compute step, never on a login node')
    allowed=sorted(os.sched_getaffinity(0))
    if len(allowed)<32:raise ValueError('Driver CPU affinity has fewer than32 permitted CPUs')
    slots=Queue()
    for start in range(0,32,8):slots.put(allowed[start:start+8])
    record.update(launch_mode='one_Slurm_step_four_local_affinity_pinned_workers',
        driver_node=socket.gethostname(),driver_step=os.environ['SLURM_STEP_ID'],worker_cpu_sets=[allowed[s:s+8] for s in range(0,32,8)])
    write_json(STATE,record)
    work=read_csv(Path(record['worklist']))
    def execute(index):
        task=work[index];proof=Path('results/v14/repeat/validation')/(task['field']+'-'+task['phase']+'.json')
        if proof.is_file() and json.loads(proof.read_text()).get('native_products_validated'):
            print('OWNED_NATIVE_ALREADY_VALID',index,flush=True);return True
        env=dict(os.environ,SLURM_ARRAY_TASK_ID=str(index),SLURM_CPUS_PER_TASK='8')
        env.pop('SLURM_TRES_PER_TASK',None)
        log=Path('logs')/f'{job}-parallel-native-{index}.log'
        cpus=slots.get()
        command=['taskset','-c',','.join(map(str,cpus)),'bash','scripts/v14_repeat.sh','remaining']
        print(f'OWNED_NATIVE_START {index} {datetime.now(timezone.utc).isoformat()}',flush=True)
        try:
            with log.open('w') as stream:result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
        finally:slots.put(cpus)
        passed=result.returncode==0 and proof.is_file() and json.loads(proof.read_text()).get('native_products_validated')
        print(f'OWNED_NATIVE_END {index} {passed} {datetime.now(timezone.utc).isoformat()}',flush=True)
        return passed
    with ThreadPoolExecutor(max_workers=4) as pool:success=list(pool.map(execute,record['tasks']))
    record.update(owned_successes=sum(success),owned_attempts=len(success),
        state='owned_execution_finished',owned_end_utc=datetime.now(timezone.utc).isoformat())
    write_json(STATE,record)
    if not all(success):raise SystemExit('Some tasks failed; registered exit guard restores original queue')


def finish():
    if not STATE.is_file():return
    record=json.loads(STATE.read_text());missing=complete_grid()
    if not missing:
        own=os.environ['SLURM_JOB_ID'];info=subprocess.check_output(['scontrol','show','job','-o',MEASURE],text=True)
        if 'JobState=PENDING' not in info:raise ValueError('Final measurement state requires inspection before rebinding')
        subprocess.run(['scontrol','update','JobId='+MEASURE,'Dependency=afterok:'+own],check=True)
        subprocess.run(['scancel','--state=PENDING',ARRAY],check=True)
        record.update(state='all144_native_validated_final_measurement_rebound',
            guard_job=own,final_measurement_dependency='afterok:'+own,missing_native=[])
    else:
        result=subprocess.run(['scontrol','release',ARRAY],capture_output=True,text=True)
        live=queue()
        if any(status=='PENDING' and 'JobHeldUser' in reason for _,status,reason in live):
            raise ValueError('Fallback did not release the original pending tasks')
        record.update(state='partial_owned_products_preserved_original_queue_released',
            missing_native=missing,release_diagnostics=(result.stdout+result.stderr).strip())
    record['guard_utc']=datetime.now(timezone.utc).isoformat();write_json(STATE,record)
    print(record['state'],len(missing),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('install','run','finish'));p.add_argument('--job');a=p.parse_args()
    install(a.job) if a.mode=='install' else run() if a.mode=='run' else finish()
