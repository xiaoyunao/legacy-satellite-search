"""Run the two predeclared conditional injections alongside the frozen holdout."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from . import run
from .data import select
from .group_budget import groups, matches
from .inject import choose_sites, inject_one
from .matched_inject import decomposition
from .search import load_isochrone, scan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field')
    field_id = parser.parse_args().field
    plan = run.config_path('holdout_trials.yaml')
    trial = yaml.safe_load(plan.read_text())['fields'][field_id]
    field_plan = run.config_path('fields.yaml')
    spec = next(s for s in yaml.safe_load(field_plan.read_text())['fields']
                if s['id']==field_id and s['role']=='pilot_eval')
    root,data,cfg = run.settings()
    frozen = json.loads(run.config_path('production.json').read_text())
    if cfg != dict(frozen['recipe'],**frozen['limits']['base'],methods=['A']):
        raise ValueError('Injection settings differ from the frozen scan')
    field,sources,area,_ = run.field_cache(root,data,spec,cfg,None)
    background = select(sources,field,area,cfg)[0]
    seed = [cfg['seed'],trial['seed_offset']]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    pos = choose_sites(field,area,cfg,1,rng)[0]
    distance = trial['distance_kpc']
    rh = np.degrees(np.arctan(trial['rh_pc']/(1000*distance)))*60
    model = load_isochrone(data/'resources'/cfg['isochrone'])
    injected,t = inject_one(pos,distance,rh,trial['latent_count'],rng,field,area,cfg,
                            background,model,cKDTree(background[:,:2]),truncation=3)
    ra,dec = field.sky(*pos)
    truth = dict(ra_deg=ra,dec_deg=dec,D_kpc=distance,theta_h_arcmin=rh)
    raw,peaks,timing,cmd = scan(np.vstack([background,injected]),field,area,model,cfg)
    base = run.read_csv(Path('results/summary')/f'{field_id}-base'/'deduplicated_peaks.csv')
    cutoff = next(p['cutoff'] for p in frozen['thresholds'] if p['budget']==frozen['primary_budget'])
    columns = ('x','y','ra_deg','dec_deg','score','dm','rh_arcmin')
    blank = [{k:float(r[k]) for k in columns} for r in base
             if r['branch']=='main' and float(r['score'])>=cutoff]
    full = [r for r in peaks if r['branch']=='main' and r['score']>=cutoff]
    pre,post = (matches(groups([dict(r,channel='A_base',ranking=r['score']) for r in table]),
                        truth,cutoff,cfg) for table in (blank,full))
    diagnostic = decomposition(raw,peaks,cmd,background,injected,field,area,pos,distance,rh,cfg)
    dest = Path('results/holdout_controls')
    dest.mkdir(exist_ok=True,parents=True)
    run.write_csv(dest/f'{field_id}.csv',[dict(field=field_id,**{**trial,**t},baseline_group=pre['spatial'],
                 cutoff=cutoff,trial_plan_sha256=run.sha(plan),seconds=sum(timing.values()),**post,**diagnostic)])


if __name__=='__main__':
    main()
