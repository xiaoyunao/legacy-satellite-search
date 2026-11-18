"""Reconcile terminal scan tasks and missing manifests against live retry coverage."""
import argparse
from datetime import datetime, timezone
import getpass
import io
import csv
import json
from pathlib import Path
import re
import subprocess

import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run(output, extra_jobs=()):
    dispatch=Path('logs/v14-dispatch.json')
    scans=json.loads(dispatch.read_text())
    primary={str(item['job']):cohort for cohort,items in scans.items() for item in items}
    old_retry=Path('results/v14/progress_20261118/retry_manifest.csv')
    requested=read_csv(old_retry)
    job_ids=[*primary,'61510268','61510994','61511922','61510733',*extra_jobs]
    command=['sacct','-j',','.join(job_ids),'-X','--array','-P',
             '--format=JobID,JobName%60,State,ExitCode,Elapsed,ReqMem,QOS,Reason%100,Start,End']
    tasks=list(csv.DictReader(io.StringIO(subprocess.check_output(command,text=True)),delimiter='|'))
    live={};terminal={}
    specs={cohort:yaml.safe_load(Path(f'configs/v14/cohorts/{cohort}/fields.yaml').read_text())['fields']
           for cohort in scans}
    for task in tasks:
        matched=re.fullmatch(r'(\d+)_(\d+)',task['JobID'])
        if not matched:
            continue
        parent,index=matched[1],int(matched[2])
        if parent in primary:
            cohort=primary[parent]
            fields=specs[cohort][index*8:(index+1)*8]
        elif parent=='61510268':
            if index>=len(requested):
                raise ValueError('Unexpected registered retry task index')
            fields=[dict(id=requested[index]['field'])]
        else:
            continue
        state=task['State'].split()[0].removesuffix('+')
        active=state in ('PENDING','RUNNING','COMPLETING','CONFIGURING','REQUEUED','SUSPENDED','RESIZING')
        terminal_states={'COMPLETED','CANCELLED','FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL',
                         'BOOT_FAIL','DEADLINE','PREEMPTED','REVOKED','SPECIAL_EXIT'}
        if not active and state not in terminal_states:
            raise ValueError(f'Unresolved Slurm state {state}; refusing to infer retry eligibility')
        target=live if active else terminal
        for field in fields:
            target.setdefault(field['id'],[]).append(task['JobID'])
    fields=read_csv(output/'fields.csv')
    candidates={r['field'] for r in requested}
    candidates.update(terminal)
    reports=[];retry=[]
    for row in fields:
        if row['field'] not in candidates:
            continue
        if row['status'] in ('complete','no_usable_gr'):
            if row['field'] not in {r['field'] for r in requested}:
                continue
            action='accepted_manifest'
        elif row['field'] in live:
            action='covered_by_live_job'
        else:
            action='submit_retry'
            retry.append(dict(cohort=row['cohort'],index=row['index'],field=row['field'],
                              previous_status=row['status']))
        reports.append(dict(cohort=row['cohort'],index=row['index'],field=row['field'],
                     manifest_status=row['status'],action=action,
                     live_jobs='|'.join(live.get(row['field'],[])),
                     terminal_jobs='|'.join(terminal.get(row['field'],[]))))
    write_csv(output/'retry_followup.csv',reports)
    write_csv(output/'uncovered_retries.csv',retry,keys=('cohort','index','field','previous_status'))
    write_csv(output/'scan_job_status.csv',tasks)
    queue=subprocess.check_output(['squeue','-u',getpass.getuser(),'-h','-o','%i|%j|%T|%r|%M'],text=True)
    stamp=datetime.now(timezone.utc).isoformat()
    write_json(output/'queue.json',dict(utc=stamp,rows=[r for r in queue.splitlines() if '|ls14' in r]))
    write_json(output/'continuation.json',dict(utc=stamp,requested_retry_count=len(requested),
        accepted=sum(r['action']=='accepted_manifest' for r in reports),
        live_covered=sum(r['action']=='covered_by_live_job' for r in reports),
        uncovered=len(retry),dispatch_sha256=sha(dispatch),audit_sha256=sha(output/'fields.csv'),
        original_retry_sha256=sha(old_retry),sacct_command=command,
        note='Terminal Slurm tasks are intersected with incomplete manifests. Existing queued/running retries are retained.'))
    print(dict(original_requests=len(requested),accepted=sum(r['action']=='accepted_manifest' for r in reports),
               covered=sum(r['action']=='covered_by_live_job' for r in reports),new_retries=len(retry)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--extra-jobs',nargs='*',default=())
    args=parser.parse_args();run(args.output,args.extra_jobs)
