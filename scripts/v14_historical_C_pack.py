"""Execute a frozen bounded partition of the historical C field manifest."""
import json
import os
from pathlib import Path

from ls_satsearch.run import sha
from scripts.v14_historical_C import BASE,run


if __name__=='__main__':
    plan=json.loads((BASE/'packs.json').read_text())
    if sha(BASE/'registration.json')!=plan['registration_sha256']:
        raise ValueError('Historical C registration changed')
    index=int(os.environ['SLURM_ARRAY_TASK_ID'])
    selected=next(p for p in plan['packs'] if p['pack']==index)
    for task in selected['tasks']:
        print('Registered historical field task',task,flush=True)
        run(task)
