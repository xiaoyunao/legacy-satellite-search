"""Verify a real unchanged A-seeded C fit and its new immutable membership artifact."""
import json
import os
from pathlib import Path

import numpy as np

from ls_satsearch.review import membership_path,review_sky_groups
from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v14_review_integrity import verify


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Use a NERSC CPU allocation')
    old=Path('results/v14/candidate_review/v14_euclid_context_20261119/north/282')
    source=read_csv(old/'review_modes.csv')
    group=min(r['group_id'] for r in source)
    selected=[r for r in source if r['group_id']==group]
    out=Path('results/v14/membership_validation');out.mkdir(parents=True,exist_ok=True)
    table=out/'review_modes.csv';write_csv(table,selected)
    data=Path(os.environ['LS_SAT_DATA'])
    os.environ['LS_SAT_CONFIG_DIR']=str(Path('configs/v14/cohorts/north').resolve())
    os.environ['LS_SAT_RUN_VERSION']='v14'
    review_sky_groups(table,'A_base',.3,archived_run=Path('regional_v14_north/results'),archive_version='v14',
        products=data/'runs/v14/membership_validation',blind_reference=True)
    reference={int(float(r['rank'])):r for r in read_csv(old/'group_review_modes.csv') if r['candidate_group_id']==group}
    rows=read_csv(out/'group_review_modes.csv');proofs=[]
    for row in rows:
        if row['fit_status']!='complete':raise ValueError('Real smoke fit incomplete')
        rank=int(float(row['rank']));prior=reference[rank]
        for key in ('ts','richness','profile_integral','fit_dm','fit_rh_arcmin','C_refit_TS_without_top3'):
            if not np.isclose(float(row[key]),float(prior[key]),rtol=1e-6,atol=1e-6):
                raise ValueError('Membership storage changed the numerical C result: '+key)
        artifact=membership_path(data,row,None)
        with np.load(artifact,allow_pickle=False) as saved:proof=verify(row,saved['source_ids'],saved['probability'])
        proofs.append(dict(rank=rank,**proof,membership_sha256=row['membership_sha256'],
            membership_data_path=row['membership_data_path'],unchanged_fit_verified=True))
    write_json(out/'acceptance.json',dict(job=os.environ['SLURM_JOB_ID'],selected_group=group,
        selection_rule='Lexicographically first ordinary A group in the already completed field; all its retained modes.',
        old_modes_sha256=sha(old/'group_review_modes.csv'),selection_sha256=sha(table),
        new_modes_sha256=sha(out/'group_review_modes.csv'),code_sha256=sha(Path('src/ls_satsearch/review.py')),
        modes=proofs,scope='Storage/integrity validation of an already fitted discovery hypothesis. No new discovery, independent evidence, C parameter optimization or change to the frozen 75 packet. Per-star arrays remain on NERSC.'))
    print('REAL_MEMBERSHIP_ARTIFACT_VERIFIED',len(proofs),flush=True)


if __name__=='__main__':run()
