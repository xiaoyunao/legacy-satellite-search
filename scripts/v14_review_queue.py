"""Temporarily order this project's queued bulk scans after the review chain."""
import argparse
import json
from pathlib import Path
import re
import subprocess

LEDGER=Path('logs/v14-review-queue-order.json')
BULK=('61469835','61469842','61469845','61469848','61469850','61469851')


def call(*cmd):
    return subprocess.check_output(cmd,text=True).strip()


def restore():
    record=json.loads(LEDGER.read_text())
    for item in record['jobs']:
        if not item['applied'] or item.get('restored'):continue
        active=call('squeue','-h','-j',item['job'],'-o','%i')
        if active:
            call('scontrol','update',f'JobId={item["job"]}',f'Nice={item["original_nice"]}')
        item['restored']=True
        LEDGER.write_text(json.dumps(record,indent=2)+'\n')
    print('Original bulk-scan scheduling restored',flush=True)


def order():
    if LEDGER.exists():raise ValueError('Queue-order ledger exists; inspect before any repeated mutation')
    record=dict(scope='Only six registered project bulk-scan parents. Existing running allocations, retries and unrelated jobs are untouched. Positive Nice lowers pending priority without cancelling work.',jobs=[])
    for job in BULK:
        row=call('scontrol','show','job','-o',job)
        if not re.search(r'JobName=ls14-south_',row):raise ValueError('Unexpected job identity')
        nice=int(re.search(r'\bNice=(\d+)',row).group(1))
        record['jobs'].append(dict(job=job,original_nice=nice,applied=False))
    LEDGER.write_text(json.dumps(record,indent=2)+'\n')
    try:
        for item in record['jobs']:
            call('scontrol','update',f'JobId={item["job"]}',f'Nice={item["original_nice"]+1000}')
            item['applied']=True;LEDGER.write_text(json.dumps(record,indent=2)+'\n')
    except Exception:
        restore();raise
    print('Review chain ordered ahead of six queued bulk-scan parents',flush=True)


def after_c():
    states=call('sacct','-X','-n','-P','-j','61556312','--format=State').splitlines()
    if states and all(s.strip('| ')=='COMPLETED' for s in states):
        job=call('sbatch','--parsable','-A','desi','-q','debug','-C','cpu','-N','1',
            '--ntasks=1','--cpus-per-task=1','--mem=1G','-t','00:05:00',
            '--dependency=afterany:61558007','--job-name=ls14-restore-review-order',
            '--output=logs/ls14-restore-review-order-%j.out',
            '--wrap','python scripts/v14_review_queue.py restore')
        print('Bulk queue restoration follows evidence job:',job,flush=True)
    else:
        # A failed C chain cannot leave the bulk queue indefinitely reduced.
        restore()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('order','restore','after-c'));args=parser.parse_args()
    {'order':order,'restore':restore,'after-c':after_c}[args.mode]()
