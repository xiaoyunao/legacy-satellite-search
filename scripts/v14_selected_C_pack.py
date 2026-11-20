"""Run disjoint registered selected-C tasks in one bounded allocated CPU step."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os

from ls_satsearch.run import read_csv,write_json
from scripts.v14_selected_C import OUT,run


def worker(item):
    cpu,indices=item;os.sched_setaffinity(0,{cpu});os.environ['SLURM_CPUS_PER_TASK']='1'
    status=[]
    for index in indices:
        try:
            run(index);status.append(dict(task=index,state='accepted'))
        except Exception as error:
            status.append(dict(task=index,state='failed',error_type=type(error).__name__,error=str(error)))
    return status


def execute(indices=None):
    if not os.getenv('SLURM_JOB_ID') or not os.getenv('SLURM_STEP_ID','').isdigit():
        raise RuntimeError('Run in an allocated CPU step')
    tasks=read_csv(OUT/'tasks.csv');indices=list(range(len(tasks))) if indices is None else indices
    if len(set(indices))!=len(indices) or any(i<0 or i>=len(tasks) for i in indices):
        raise ValueError('Only disjoint registered task indices are allowed')
    cpus=sorted(os.sched_getaffinity(0));workers=min(8,len(cpus),len(indices))
    if not workers:raise ValueError('No registered C tasks')
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results=[r for group in pool.map(worker,[(cpus[i],indices[i::workers]) for i in range(workers)]) for r in group]
    write_json(OUT/f"pack_{os.environ['SLURM_JOB_ID']}.json",dict(job=os.environ['SLURM_JOB_ID'],
        workers=workers,results=results,identities_private=True))
    print(dict(tasks=len(results),failed=sum(r['state']=='failed' for r in results)),flush=True)
    if any(r['state']=='failed' for r in results):raise RuntimeError('Preserve accepted tasks and retry actual failed manifest only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--indices',type=int,nargs='+')
    execute(parser.parse_args().indices)
