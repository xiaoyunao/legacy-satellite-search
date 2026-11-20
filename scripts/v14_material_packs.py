"""Pack remaining registered record renders; never change the selected sample."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

from ls_satsearch.run import read_csv,sha,write_json
from scripts.v14_prepare_record_task import run

ROOT=Path('results/v14/human_review/final_private')
SOURCE=ROOT/'final_record_preparation/plan.json'
OUTPUT=ROOT/'material_packs'


def register():
    if OUTPUT.exists():raise ValueError('Preserve registered work allocation')
    plan=json.loads(SOURCE.read_text());tasks=[];reused=0
    for i,spec in enumerate(plan['fields']):
        accepted=ROOT/'prepared_records'/spec['record_key']/'accepted.json'
        if accepted.exists():
            proof=json.loads(accepted.read_text())
            if (proof['source_detection_id']!=spec['source_detection_id'] or
                    proof['source_input_sha256'][proof['source_spec']['fits']]!=sha(Path(spec['fits']))):
                raise ValueError('Cached record belongs to another original fit')
            reused+=1;continue
        rows=read_csv(Path(spec['fits']))
        weight=20+sum(35+.1*float(r['fit_rh_arcmin'])**2 for r in rows)
        tasks.append(dict(index=i,modes=len(rows),estimated_seconds=weight))
    slots=[[] for _ in range(24)];loads=[0.]*24
    for item in sorted(tasks,key=lambda t:(-t['estimated_seconds'],t['index'])):
        position=min(range(24),key=lambda k:(loads[k],k));slots[position].append(item['index']);loads[position]+=item['estimated_seconds']
    OUTPUT.mkdir(parents=True)
    write_json(OUTPUT/'registration.json',dict(source_plan=str(SOURCE),source_plan_sha256=sha(SOURCE),
        implementations={str(p):sha(p) for p in map(Path,('scripts/v14_material_packs.py','scripts/v14_prepare_record_task.py',
            'scripts/v14_reuse_frozen_record.py','scripts/v14_prepare_record.py'))},
        records_total=len(plan['fields']),records_already_accepted=reused,pending_records=len(tasks),
        pending_modes=sum(t['modes'] for t in tasks),resource_rule='Three packs of eight disjoint one-CPU workers. Greedy fixed estimate20s/record+sum(35+0.1rh_arcmin²)s/mode; resource estimate only, no selection rule.',
        packs=[dict(index=i,workers=[slots[j] for j in range(i,24,3)],
            maximum_estimated_worker_seconds=max(loads[j] for j in range(i,24,3))) for i in range(3)]))
    print(dict(total_records=len(plan['fields']),reused=reused,pending_records=len(tasks),pending_modes=sum(t['modes'] for t in tasks),max_estimated_seconds=max(loads)),flush=True)


def worker(item):
    cpu,indices=item;os.sched_setaffinity(0,{cpu});os.environ['SLURM_CPUS_PER_TASK']='1';result=[]
    for index in indices:
        try:run(SOURCE,index);result.append(dict(index=index,state='accepted'))
        except Exception as error:result.append(dict(index=index,state='failed',error_type=type(error).__name__,error=str(error)))
    return result


def execute(index):
    if not os.getenv('SLURM_JOB_ID') or not os.getenv('SLURM_STEP_ID','').isdigit():raise RuntimeError('Use an allocated eight-CPU step')
    path=OUTPUT/'registration.json';plan=json.loads(path.read_text())
    if sha(SOURCE)!=plan['source_plan_sha256']:raise ValueError('Selected material plan changed')
    for name,digest in plan['implementations'].items():
        if sha(Path(name))!=digest:raise ValueError('Registered material implementation changed')
    pack=next(p for p in plan['packs'] if p['index']==index);cpus=sorted(os.sched_getaffinity(0))
    if len(cpus)<8:raise ValueError('Eight independent worker CPUs required')
    with ProcessPoolExecutor(max_workers=8) as pool:
        results=[r for group in pool.map(worker,[(cpus[i],indices) for i,indices in enumerate(pack['workers'])]) for r in group]
    write_json(OUTPUT/f"result_{os.environ['SLURM_JOB_ID']}_{index}.json",dict(job=os.environ['SLURM_JOB_ID'],
        pack=index,registration_sha256=sha(path),results=results))
    print(dict(pack=index,records=len(results),failed=sum(r['state']=='failed' for r in results)),flush=True)
    if any(r['state']=='failed' for r in results):raise RuntimeError('Retain accepted records; inspect failed record manifest only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('register','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args();register() if args.mode=='register' else execute(args.index)
