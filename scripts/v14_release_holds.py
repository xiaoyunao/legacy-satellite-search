"""Release only recorded original pending holds if an interactive handoff exits."""
import argparse
import json
from pathlib import Path
import subprocess


def release(path):
    record=json.loads(path.read_text());actions=[]
    for job in record['original_arrays']:
        output=subprocess.check_output(['squeue','-h','-r','-j',job,'-o','%i|%T|%R'],text=True)
        held=[r for r in output.splitlines() if '|PENDING|' in r and 'JobHeldUser' in r]
        if held:
            subprocess.run(['scontrol','release',job],check=True)
            actions.append(dict(job=job,action='released_original_pending_hold',tasks=len(held)))
    record['fallback_actions']=actions
    record['fallback_checked']=True
    path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(actions),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger',type=Path);args=parser.parse_args();release(args.ledger)
