"""Run only a terminal pack's registered unaccepted records, one per worker."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

from ls_satsearch.run import sha,write_json
from scripts.v14_material_packs import SOURCE,OUTPUT,worker


def execute(worklist):
    if not os.getenv('SLURM_JOB_ID') or not os.getenv('SLURM_STEP_ID','').isdigit():
        raise RuntimeError('Use an allocated CPU step')
    retry=json.loads(worklist.read_text());original=json.loads((OUTPUT/'registration.json').read_text())
    if (sha(SOURCE)!=original['source_plan_sha256']
            or sha(OUTPUT/'registration.json')!=retry['original_registration_sha256']):
        raise ValueError('Registered material source changed')
    for name,digest in original['implementations'].items():
        if sha(Path(name))!=digest:raise ValueError('Frozen renderer/worker changed')
    indices=retry['indices'];cpus=sorted(os.sched_getaffinity(0))
    if len(indices)!=len(set(indices)) or len(indices)>len(cpus):
        raise ValueError('Require one available CPU per unique retry record')
    with ProcessPoolExecutor(max_workers=len(indices)) as pool:
        results=[r for group in pool.map(worker,[(cpus[i],[index]) for i,index in enumerate(indices)]) for r in group]
    write_json(worklist.with_name('result_'+os.environ['SLURM_JOB_ID']+'.json'),
        dict(worklist_sha256=sha(worklist),job=os.environ['SLURM_JOB_ID'],results=results))
    print(dict(records=len(results),failed=sum(r['state']=='failed' for r in results)),flush=True)
    if any(r['state']=='failed' for r in results):raise RuntimeError('Inspect actual failed records only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worklist',type=Path,required=True)
    execute(parser.parse_args().worklist)
