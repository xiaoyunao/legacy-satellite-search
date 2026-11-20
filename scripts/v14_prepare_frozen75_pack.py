"""Run registered independent evidence cases within one allocated CPU node."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
from ls_satsearch.run import sha,write_json

PLAN=Path('configs/v14_review_preparation/packs.json')


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    plan=json.loads(PLAN.read_text())
    for p,d in plan['implementation_sha256'].items():
        if sha(Path(p))!=d:raise ValueError('Registered rendering implementation changed: '+p)
    index=int(os.environ['SLURM_ARRAY_TASK_ID']);tasks=plan['packs'][index]
    folder=Path('logs')/f'prepare75-{os.environ["SLURM_JOB_ID"]}';folder.mkdir(exist_ok=True)
    def execute(i):
        with (folder/f'{i:02d}.log').open('w') as stream:
            result=subprocess.run([sys.executable,'-u','-m','scripts.v14_prepare_frozen75',str(i)],
                                  stdout=stream,stderr=subprocess.STDOUT)
        return dict(index=i,returncode=result.returncode)
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(execute,i) for i in tasks]
        for future in as_completed(futures):
            row=future.result();rows.append(row);print(json.dumps(row),flush=True)
    out=Path('results/v14/human_review/final_private/prepared75/packs')
    out.mkdir(exist_ok=True)
    write_json(out/f'{os.environ["SLURM_JOB_ID"]}.json',dict(job=os.environ['SLURM_JOB_ID'],index=index,
        plan_sha256=sha(PLAN),runner_sha256=sha(Path(__file__)),cases=rows,
        all_completed=all(r['returncode']==0 for r in rows),final_review_release=False))
    if any(r['returncode'] for r in rows):raise SystemExit(1)


if __name__=='__main__':main()
