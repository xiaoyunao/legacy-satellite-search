"""Compare the frozen target with similarly observed A-selected compact peaks."""

import argparse
import json
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv, write_csv


def compare(archive,output,target):
    modes={(r['candidate_group_id'],r['rank']):r
           for f in (archive/'batches').glob('*/results/holdout/group_review_modes.csv')
           for r in read_csv(f) if r['fit_status']=='complete'}
    compact=[r for r in read_csv(archive/'expansion/pilot_candidate_summary.csv')
             if r['phase']=='discovery' and float(r['best_rh'])<=1]
    attributes=('g_depth_local_p10_p50_p90','g_seeing_local_p10_p50_p90','ebv_local_p10_p50_p90')
    rows=[]
    features=[]
    for group in compact:
        m=modes[group['group_id'],group['best_peak_rank']]
        if not all(m[k] for k in attributes):
            continue
        values=[json.loads(m[k])[1] for k in attributes]
        features.append([*values,float(m['bg_per_arcmin2'])])
        rows.append(dict(group_id=group['group_id'],A_score=float(m['discovery_score']),
                         C_TS=float(m['ts']),C_residual_TS=float(m['C_refit_TS_without_top3']),
                         g_depth=values[0],g_seeing=values[1],ebv=values[2],
                         psf_density=float(m['bg_per_arcmin2'])))
    v=np.asarray(features)
    i=next(i for i,r in enumerate(rows) if r['group_id']==target)
    scale=np.maximum(v.std(axis=0),[.02,.02,.002,.1])
    d=np.linalg.norm((v-v[i])/scale,axis=1)
    chosen=[i,*[j for j in np.argsort(d) if j!=i][:16]]
    write_csv(output,[dict(rows[j],target=j==i,condition_distance=float(d[j]),
                          eligible_compact_groups=len(v)) for j in chosen])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--target',default='expand_03-A_base-0.3-003')
    a=p.parse_args()
    compare(a.archive,a.output,a.target)
