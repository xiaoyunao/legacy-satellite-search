"""Compare unchanged C numerics with immediate versus deferred diagnostic rendering."""
import inspect
import json
import os
from pathlib import Path
from time import perf_counter

import numpy as np

from ls_satsearch.review import fit_at_peak, review_sky_groups
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    root=Path('results/v14/production_integration/C_rendering_pilot')
    source=Path('results/v14/candidate_review/v14/south_delve/04/review_modes.csv')
    config=Path('configs/v14/cohorts/south_delve/search.yaml')
    checksums={str(p):sha(p) for p in (source,config,Path('src/ls_satsearch/review.py'),Path('src/ls_satsearch/search.py'))}
    if (root/'acceptance.json').exists():raise ValueError('Pilot already accepted; preserve its results')
    rows=read_csv(source);selected=[r for r in rows if r['field']==rows[0]['field']][:2]
    if len(selected)!=2:raise ValueError('Two existing retained modes required')
    data=Path(os.environ['LS_SAT_DATA']);os.environ['LS_SAT_CONFIG_DIR']='configs/v14/cohorts/south_delve'
    fits={};elapsed={}
    for render,label in ((True,'immediate'),(False,'deferred')):
        folder=root/label;folder.mkdir(parents=True,exist_ok=True)
        table=folder/'review_modes.csv';write_csv(table,selected)
        os.environ['LS_SAT_RUN_VERSION']='v14_rendering_pilot_'+label
        products=data/'runs/v14/rendering_pilot'/label
        started=perf_counter()
        review_sky_groups(table,'A_base',.3,archived_run=Path('regional_v14_south_delve/results'),
                          archive_version='v14',products=products,blind_reference=True,render_diagnostics=render)
        elapsed[label]=perf_counter()-started
        fits[label]=read_csv(folder/'group_review_modes.csv')
        write_json(folder/'execution.json',dict(job=os.getenv('SLURM_JOB_ID'),render_diagnostics=render,
                    elapsed_seconds=elapsed[label],inputs=checksums,selection_sha256=sha(table),
                    products=str(products),scope='Two retained production modes, diagnostic-equivalence pilot only. Not a complete production source record or extra blind recovery.'))
    excluded={'g_depth_local_p10_p50_p90','g_seeing_local_p10_p50_p90','ebv_local_p10_p50_p90'}
    compare=[]
    for a,b in zip(fits['immediate'],fits['deferred']):
        if a['fit_status']!='complete' or b['fit_status']!='complete':raise ValueError('Pilot C fit incomplete')
        keys=[k for k in a if k in b and k not in excluded and not k.startswith('image_')
              and k not in ('g_centre','r_centre') and not k.startswith(('g_source','r_source'))]
        if any(a[k]!=b[k] for k in keys):raise ValueError('C scientific row changed with rendering policy')
        for row in (a,b):
            path=data/row['membership_data_path']
            if sha(path)!=row['membership_sha256']:raise ValueError('Membership bytes changed')
        with np.load(data/a['membership_data_path'],allow_pickle=False) as x,np.load(data/b['membership_data_path'],allow_pickle=False) as y:
            if not np.array_equal(x['source_ids'],y['source_ids']) or not np.array_equal(x['probability'],y['probability']):raise ValueError('Fitted source IDs or probabilities changed')
        if b['image_pending']!='True' or b['diagnostics_deferred']!='True' or b['image_diagnostic_generated']!='False':raise ValueError('Deferred evidence incorrectly marked available')
        compare.append(dict(ts=a['ts'],fit_dm=a['fit_dm'],fit_rh_arcmin=a['fit_rh_arcmin'],
                            compared_scientific_columns=len(keys),identical=True,membership_arrays_identical=True))
    if len(compare)!=2:raise ValueError('Pilot lost a seed')
    if any(sha(Path(p))!=v for p,v in checksums.items()):raise ValueError('Input or implementation changed during pilot')
    write_json(root/'acceptance.json',dict(job=os.getenv('SLURM_JOB_ID'),inputs=checksums,
        pilot_code_sha256=sha(Path(__file__)),elapsed_seconds=elapsed,comparisons=compare,
        all_scientific_columns_and_memberships_identical=True,deferred_evidence_remains_pending=True,
        scope='Ordered warm-cache two-mode equivalence test; elapsed times are not an unbiased full-workflow speedup measurement. Numerical fitting, mask/selection, top-source deletions and membership are unchanged. Raw-template-peak I/O used only by plotting is deferred too. No production completion, human grade or candidate evidence upgrade.'))
    print(json.dumps(dict(job=os.getenv('SLURM_JOB_ID'),elapsed=elapsed,scientific_equivalence_passed=True)),flush=True)


if __name__=='__main__':run()
