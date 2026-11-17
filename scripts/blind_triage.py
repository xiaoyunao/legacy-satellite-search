"""Sample the prior low-priority queue and seal shuffled panel identities."""

import argparse
import csv
from pathlib import Path

import numpy as np
import yaml


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def run(policy, output):
    rule = yaml.safe_load(policy.read_text())
    rng = np.random.default_rng(rule['seed'])
    manual = {r['group_id'] for r in read(Path('results/v8/rollout/visual_review.csv'))}
    ids = read(Path('results/v8/rollout/candidate_index.csv'))
    pool = sorted((r for r in ids if r['known_context']=='untagged' and r['manual_priority']=='0'
                   and r['group_id'] not in manual and r['best_peak_rank']),
                  key=lambda r: (float(r['best_ts']),r['group_id']))
    selected = []
    for compact in (False, True):
        for mask in (False, True):
            rows = [r for r in pool if (float(r['best_rh'])<=rule['compact_cut_arcmin'])==compact and
                    (float(r['nearest_mask_hole_arcmin'] or 'inf')<=rule['mask_context_arcmin'])==mask]
            for b, indices in enumerate(np.array_split(np.arange(len(rows)),rule['ts_strata']),1):
                chosen=rng.choice(indices,min(rule['per_stratum'],len(indices)),replace=False)
                for i in chosen:
                    r=rows[i]
                    selected.append(dict(group_id=r['group_id'],stratum=f"compact_{int(compact)}_mask_{int(mask)}_ts_{b}",
                                         stratum_size=len(indices),stratum_selected=len(chosen),
                                         origin='rollout',directory=r['diagnostic_directory'],rank=r['best_peak_rank']))
    if len(selected)!=rule['low_priority_count']:
        raise ValueError(f"Requested sample size unavailable across frozen strata: {len(selected)}")
    weak = read(Path('results/v5/weak/holdout/weak_reference_association.csv'))
    baseline7=next(r for r in read(Path('results/v6/verification/depth_DELVE_7.csv')) if r['arm']=='ls_base')
    if baseline7['spatial']!='False':
        raise ValueError('DELVE 7 baseline control requires a retrospective visual panel')
    for name in rule['weak_controls']:
        valid=[r for r in weak if r['object']==name and r['preferred_C']=='True' and r['detected']=='True']
        if not valid and name==baseline7['field']:
            continue
        if not valid:
            raise ValueError(f'Missing archived control {name}')
        best=max(valid,key=lambda r:float(r['C_TS']))
        selected.append(dict(group_id=best['group_id'],stratum='',stratum_size='',stratum_selected='',
                             origin=name,directory=f"results/v5/weak/figures/{best['field']}-base",rank=best['rank']))
    rng.shuffle(selected)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,['blind_id',*selected[0]],lineterminator='\n')
        writer.writeheader()
        writer.writerows(dict(blind_id=f'B{i:02d}',**r) for i,r in enumerate(selected,1))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,default=Path('configs/v9/blind_triage.yaml'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.policy,args.output)
