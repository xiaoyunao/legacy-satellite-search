"""Paired baseline/deep catalog injections on the same generated populations."""

import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree
from scipy.stats import binomtest

from .data import select
from .inject import inject_one, match_trial
from .run import config_path, coverage_metrics, field_cache, read_csv, settings, write_csv, write_json
from .search import load_isochrone, scan


def run(field_id, radius, mismatch=False, legacy_locus=False):
    root, data_root, base = settings()
    deep = dict(base, g_max=base['g_max']+.5, r_max=base['r_max']+.5)
    spec = next(f for f in yaml.safe_load(config_path('fields.yaml').read_text())['fields'] if f['id']==field_id)
    if spec['role'] != 'pilot_dev':
        raise ValueError('Injections use the frozen development fields')
    field, data, area, _ = field_cache(root,data_root,spec,base,None)
    background = {name:select(data,field,area,cfg)[0] for name,cfg in (('base',base),('deep',deep))}
    tree = cKDTree(background['deep'][:,:2])
    template = data_root/'resources'/base['isochrone']
    model = load_isochrone(template,legacy_locus=legacy_locus)
    injected_model = load_isochrone(template.with_name('iso_a10.0_z0.00010.dat')) if mismatch else model
    rng = np.random.default_rng(np.random.SeedSequence([base['seed'], radius, int(spec['ra']*1000)]))
    conditions = list(product((50,100),(12,22,36)))
    rng.shuffle(conditions)
    sites = [(x,y) for y in (-44,0,44) for x in (-27,27)]
    truth, stars = [], {'base':[], 'deep':[]}
    for i, ((distance,n),(x,y)) in enumerate(zip(conditions,sites)):
        rh = np.degrees(np.arctan(radius/(1000*distance)))*60
        pos = np.array([x,y]) + rng.uniform(-2,2,size=2)
        if coverage_metrics(field, area, base, limit=max(4,3*rh), center=pos) < .80:
            raise RuntimeError(f'Poor joint sky coverage at site {i} in {field_id}')
        eligible, t = inject_one(pos,distance,rh,n,rng,field,area,deep,background['deep'],
                                 injected_model,tree,truncation=3)
        shallow = eligible[np.all(eligible[:,2:4] <= [base['g_max'],base['r_max']],axis=1)]
        truth.append(dict(t, trial=i, rh_pc=radius, N_base=len(shallow), N_deep=len(eligible),
                          generation_age=10 if mismatch else 12))
        stars['base'].append(shallow)
        stars['deep'].append(eligible)
    rows = []
    timing = {}
    for depth,cfg in (('base',base),('deep',deep)):
        reference = read_csv(Path('results/summary')/f'{field_id}-{depth}/deduplicated_peaks.csv')
        _, found, timing[depth], _ = scan(np.concatenate([background[depth],*stars[depth]]),field,area,model,cfg)
        for t in truth:
            for method in ('A','B'):
                peak = match_trial(found,t,method,base) or {}
                blank = match_trial(reference,t,method,base) or {}
                rows.append(dict(t,field=field_id,method=method,depth=depth,
                                 injected_score=peak.get('score'), blank_score=blank.get('score'),
                                 found_dm=peak.get('dm'), found_rank=peak.get('rank')))
    output=Path('results/summary')/('legacy_locus_trials' if legacy_locus else 'paired_trials')
    output.mkdir(exist_ok=True,parents=True)
    name=f'{field_id}-{radius}pc-{10 if mismatch else 12}gyr'
    write_csv(output/f'{name}.csv',rows)
    write_json(output/f'{name}.json',dict(timing=timing,seed=base['seed'],rng_keys=[radius,int(spec['ra']*1000)],
                                         truncate_rh=3,legacy_locus=legacy_locus,field=field_id))


def combine(dest=Path('results/summary')):
    cuts={(r['method'],r['budget'],r['depth']):r['cutoff']
          for r in json.loads((dest/'review_cutoffs.json').read_text()) if r['branch']=='main'}
    pairs={}
    for path in sorted((dest/'paired_trials').glob('*.csv')):
        for r in read_csv(path):
            pairs.setdefault((path.stem,r['trial'],r['method']),{})[r['depth']]=r
    report=[]
    for budget in sorted({b for _,b,_ in cuts}):
        counts={}
        for pair in pairs.values():
            base,deep=(pair[d] for d in ('base','deep'))
            key=(base['method'],base['generation_age'],base['distance_kpc'],base['rh_pc'])
            q=counts.setdefault(key,dict(base_only=0,deep_only=0,both=0,neither=0,blank_excluded=0))
            limits=[cuts.get((r['method'],budget,r['depth'])) for r in (base,deep)]
            if None in limits:
                continue
            if any(r['blank_score'] and float(r['blank_score'])>=limit for r,limit in zip((base,deep),limits)):
                q['blank_excluded']+=1
                continue
            x,y=(bool(r['injected_score'] and float(r['injected_score'])>=limit)
                 for r,limit in zip((base,deep),limits))
            q[{(True,False):'base_only',(False,True):'deep_only',(True,True):'both',(False,False):'neither'}[x,y]]+=1
        for (method,age,distance,radius),q in counts.items():
            n=q['both']+q['neither']+q['base_only']+q['deep_only']
            discordant=q['base_only']+q['deep_only']
            report.append(dict(method=method,budget=budget,generation_age=age,distance_kpc=distance,
                               rh_pc=radius,n_pairs=n,**q,paired_delta=(q['deep_only']-q['base_only'])/n if n else None,
                               discordant_exact_p=binomtest(q['deep_only'],discordant).pvalue if discordant else None))
    if report:
        write_csv(dest/'paired_depth_summary.csv',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field',nargs='?')
    parser.add_argument('radius',nargs='?',type=int,choices=(10,30,80))
    parser.add_argument('--mismatch',action='store_true')
    parser.add_argument('--legacy-locus',action='store_true')
    parser.add_argument('--summary',type=Path,default=Path('results/summary'))
    args=parser.parse_args()
    if args.field:
        if args.radius is None:
            parser.error('Specify the radius in parsecs')
        run(args.field,args.radius,args.mismatch,args.legacy_locus)
    else:
        combine(args.summary)
