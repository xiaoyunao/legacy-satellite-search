"""Locate the loss of representative 80 pc catalog injections."""

import argparse
from itertools import product
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import load_bricks, sample_pixels, select
from .group_budget import groups
from .inject import match_trial
from .paired import populations
from .run import (config_path, field_cache, read_csv, runs_path, settings, sha,
                  write_csv, write_json)
from .search import binomial_tail_score, exact_onoff, load_isochrone, scan


def stages(sample, field, area, cfg, model, truth, cutoff, work):
    raw, dedup, timing, cmd = scan(sample, field, area, model, cfg)
    write_csv(work/'raw_peaks.csv',raw)
    write_csv(work/'deduplicated_peaks.csv',dedup)
    ranked = [dict(p,ranking=p['score'],channel='A_deep') for p in dedup if p['branch']=='main']
    group_list = groups(ranked)
    ranked_raw = sorted(raw,key=lambda r:-r['score'])
    p_raw,p_dedup = (match_trial(items,truth,'A',cfg) or {} for items in (ranked_raw,dedup))
    nearby_group = next(((a,h) for a,h in group_list
                         if np.hypot(a['x']-truth['x'],a['y']-truth['y']) <= max(2,truth['rh_arcmin'])),
                        ({}, []))
    anchor, alternatives = nearby_group
    passing_modes = [p for p in alternatives if p['score']>=cutoff and
                     abs(p['dm']-truth['dm'])<=cfg['match_dm_tolerance']]
    summary = dict(raw_id=p_raw.get('raw_peak_id'),raw_score=p_raw.get('score'),
                   dedup_rank=p_dedup.get('rank'),dedup_score=p_dedup.get('score'),
                   group_score=anchor.get('score'),group_dm=anchor.get('dm'),
                   group_pass=bool(anchor and anchor['score']>=cutoff),passing_modes=len(passing_modes),
                   cutoff=cutoff)
    points = []
    tree = cKDTree(sample[:,:2])
    best_grid_dm = min(np.arange(16.5,20.76,.25),key=lambda dm:abs(dm-truth['dm']))
    best_grid_rh = min(cfg['radii_arcmin'],key=lambda rh:abs(np.log(rh/truth['rh_arcmin'])))
    for name,dm,rh in (('truth',truth['dm'],truth['rh_arcmin']),('near_grid',best_grid_dm,best_grid_rh)):
        chosen,_ = cmd.weights(dm)
        ni,no,ai,ao = exact_onoff(field,truth['x'],truth['y'],rh,tree,area,chosen)
        score = binomial_tail_score(ni,ni+no,ai/(ai+ao)) if ai>0 and ao>0 else None
        points.append(dict(position='truth',template=name,dm_used=dm,scale_used=rh,n_on=ni,n_off=no,
                           area_on_arcmin2=ai,area_off_arcmin2=ao,background_per_arcmin2=no/ao if ao else None,
                           on_excess=ni-no*ai/ao if ao else None,truth_aperture_score=score))
    return summary,points,timing


def run(field_id, trial):
    root,data_root,base = settings()
    spec = next(s for s in yaml.safe_load(config_path('v2_fields.yaml').read_text())['fields']
                if s['id']==field_id and s['role']=='pilot_dev')
    field,data,area,_ = field_cache(root,data_root,spec,base,load_bricks(root))
    deep = dict(base,g_max=base['g_max']+.5,r_max=base['r_max']+.5,
                methods=['A'],dm=[16.5,20.75,.25])
    sample = select(data,field,area,deep)[0]
    model = load_isochrone(data_root/'resources'/base['isochrone'])
    seeds = [base['seed'],80,int(spec['ra']*1000)]
    rng = np.random.default_rng(np.random.SeedSequence(seeds))
    conditions = list(product((50,100),(12,22,36)))
    rng.shuffle(conditions)
    sites = [(x,y) for y in (-44,0,44) for x in (-27,27)]
    truths,stars = populations(base,deep,80,field,area,sample,model,cKDTree(sample[:,:2]),
                               rng,conditions,sites,field_id,False)
    truth = truths[trial]
    delivered = stars['deep'][trial]
    dest = Path('results/summary/wide')
    dest.mkdir(exist_ok=True,parents=True)
    archive = Path('references/v3_wide_controls.csv')
    old = next(r for r in read_csv(archive) if (r['field'],int(r['trial']))==(field_id,trial))
    if int(old['N_deep']) != len(delivered) or not np.allclose([float(old['x']),float(old['y'])],
                                                              [truth['x'],truth['y']],atol=1e-8):
        raise RuntimeError('V2 site failed exact replay checks')
    cutoff_file = Path('references/v3_archive_group_policy.json')
    cutoff = next(r['cutoff'] for r in json.loads(cutoff_file.read_text())['thresholds']
                  if r['policy']=='A_deep' and r['budget']==.3)
    # Nested increments condition on photometry that already passed catalog selection.
    q = rng.uniform(0,.9,512)
    angle = rng.uniform(0,2*np.pi,len(q))
    xy = np.array([truth['x'],truth['y']]) + truth['rh_arcmin']*np.sqrt(q/(1-q))[:,None]*np.column_stack([
        np.cos(angle),np.sin(angle)])
    valid = area[sample_pixels(field,area,*xy.T)]
    extra = np.column_stack([xy[valid],delivered[rng.integers(len(delivered),size=valid.sum()),2:]])
    scenarios = {'blank': [],'overlay':stars['deep'],'isolated':[delivered]}
    if trial == 0 and field_id == 'dev_deep':
        for n in (45,65):
            scenarios[f'isolated_N{n}'] = [delivered,extra[:n-len(delivered)]]
    output, apertures, time = [], [], {}
    for label,pieces in scenarios.items():
        work = runs_path(data_root)/'wide'/f'{field_id}-{trial}'/label
        work.mkdir(exist_ok=True,parents=True)
        values,details,time[label] = stages(np.concatenate([sample,*pieces]),field,area,deep,model,truth,cutoff,work)
        meta = dict(field=field_id,trial=trial,scenario=label,distance_kpc=truth['distance_kpc'],rh_pc=80,
                    focal_N=0 if label=='blank' else (len(delivered) if label=='overlay' else sum(map(len,pieces))),
                    total_N=sum(map(len,pieces)),v2_overlay_score=float(old['injected_score']))
        output.append(dict(meta,**values))
        apertures.extend(dict(meta,**point) for point in details)
    name = f'{field_id}-{trial}'
    write_csv(dest/f'{name}-scan.csv',output)
    write_csv(dest/f'{name}-aperture.csv',apertures)
    write_json(dest/f'{name}-manifest.json',dict(field=spec,timing=time,rng_keys=seeds,
               cutoff_policy_sha256=sha(cutoff_file),status='complete',job=os.environ.get('SLURM_JOB_ID')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    p.add_argument('trial',type=int)
    a=p.parse_args()
    run(a.field,a.trial)
