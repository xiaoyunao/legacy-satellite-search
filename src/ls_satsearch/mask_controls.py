"""Compare fitted candidate positions to area- and condition-matched random positions."""

import json
import os
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import yaml

from .data import sample_pixels, select
from .run import config_path, field_cache, read_csv, settings, sha, write_csv, write_json
from .verify_candidate import observing_proxy


def run():
    root,data,cfg=settings()
    plan=yaml.safe_load(config_path('followup.yaml').read_text())
    prior=Path(os.environ['LS_SAT_V5'])
    rows=[r for r in read_csv(prior/'results/expansion/pilot_candidate_summary.csv')
          if r['phase']=='discovery']
    rng=np.random.default_rng(plan['seed'])
    result=[]
    for ident in sorted({r['field'] for r in rows}):
        group=[r for r in rows if r['field']==ident]
        old=prior/'batches'/group[0]['batch']/'results/summary'/f'{ident}-base/manifest.json'
        spec=json.loads(old.read_text())['field']
        field,source,mask,_=field_cache(root,data,spec,cfg,None)
        step=2*field.limit/mask.shape[0]
        distance=distance_transform_edt(mask)*step
        ra=np.array([float(r['fit_ra_deg']) for r in group])
        dec=np.array([float(r['fit_dec_deg']) for r in group])
        xy=np.column_stack(field.xy(ra,dec))
        points=rng.uniform(-30*field.width,30*field.width,(plan['mask_draws'],2))
        valid=mask[sample_pixels(field,mask,*points.T)]
        points=np.vstack([xy,points[valid]])
        proxy=observing_proxy(field,source,points)
        sample,*_=select(source,field,mask,cfg)
        tree=cKDTree(sample[:,:2])
        density=tree.query_ball_point(points,4,return_length=True)-tree.query_ball_point(points,2,return_length=True)
        features=np.column_stack([proxy,density])
        normal=np.maximum(np.std(features[len(group):],axis=0),[.02,.02,.002,1.])
        control_mask_dist=distance[sample_pixels(field,mask,*points[len(group):].T)]
        for j,r in enumerate(group):
            mismatch=np.linalg.norm((features[len(group):]-features[j])/normal,axis=1)
            best=np.argsort(mismatch)[:plan['mask_neighbors']]
            if len(best)!=plan['mask_neighbors']:
                raise ValueError(f'Insufficient usable random positions in {ident}')
            d=control_mask_dist[best]
            rh=float(r['best_rh'])
            result.append(dict(group_id=r['group_id'],field=ident,rh_arcmin=rh,
                               observed_2arcmin=r['near_mask_hole_2arcmin']=='True',
                               observed_within_rh=r['mask_within_fit_rh']=='True',
                               random_near_2arcmin=float((d<=2).mean()),
                               random_within_rh=float((d<=rh).mean()),
                               random_pool=int(valid.sum()),control_count=len(best),
                               median_condition_distance=float(np.median(mismatch[best]))))
        print(f'{ident}: {len(group)} groups',flush=True)
    out=Path('results/verification')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'mask_control_groups.csv',result)
    totals={}
    for k in ('2arcmin','within_rh'):
        control='random_near_2arcmin' if k=='2arcmin' else 'random_within_rh'
        obs=np.array([r['observed_'+k] for r in result])
        null=np.array([r[control] for r in result])
        byfield=list(dict.fromkeys(r['field'] for r in result))
        fields=np.array([r['field'] for r in result])
        mult=np.random.default_rng(plan['seed']).multinomial(len(byfield),
                           np.full(len(byfield),1/len(byfield)),size=10000)
        diff=np.array([(obs-null)[fields==b].sum() for b in byfield])
        counts=np.array([(fields==b).sum() for b in byfield])
        totals[k]=dict(observed=int(obs.sum()),expected_matched=float(null.sum()),
                       difference=float((obs-null).mean()),
                       field_bootstrap_interval=(np.quantile((mult@diff)/(mult@counts),[.025,.975])).tolist())
    write_json(out/'mask_control_summary.json',dict(groups=len(result),config=sha(config_path('followup.yaml')),
               slurm=os.environ.get('SLURM_JOB_ID'),**totals))


if __name__=='__main__':
    run()
