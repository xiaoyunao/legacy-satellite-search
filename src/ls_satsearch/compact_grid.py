"""Compare matched control and development scans with and without a 0.25 arcmin kernel."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field
from .group_budget import evaluate, groups, matches
from .inject import choose_sites, inject_one
from .matched import PS1_MODEL
from .ps1_tiles import design
from .run import config_path,read_csv,recovery,settings,write_csv,write_json
from .search import load_isochrone,scan

ARMS={'fine_base':[.5,1,2,4], 'fine_compact':[.25,.5,1,2,4]}
SURVEYS=('ls_base','ps1')
IDS=('fresh_01','fresh_03','fresh_05','fresh_09','delve4','delve5')
DEST=Path('results/compact_grid')


def finer_field(spec,cohort):
    old,_ = design(spec,cohort)
    field = Field(old.ra,old.dec,old.width,old.step/2,buffer=old.limit-old.width*30-1e-6)
    if not np.isclose(old.limit,field.limit):
        raise ValueError('The finer grid changes the search boundary')
    return field


def experiment(name,archive):
    _,data,cfg = settings()
    cohort = yaml.safe_load(config_path('matched.yaml').read_text())
    spec = next(f for f in cohort['fields'] if f['id']==name)
    field = finer_field(spec,cohort)
    version='v3' if name in ('fresh_01','fresh_03') else 'v4'
    truth_table = {r['name']:r for r in read_csv(Path('references/benchmarks.csv'))}
    for survey in SURVEYS:
        raw = data/'runs'/version/'matched'/survey/name
        sample = np.load(raw/'sample.npy',allow_pickle=False)
        area = np.load(raw/'coverage.npy',allow_pickle=False)
        if area.shape!=(field.n,field.n):
            raise ValueError('The existing high resolution mask does not match the finer grid')
        prev = json.loads((archive/survey/'summary'/f'{name}-base'/'manifest.json').read_text())
        band = ('gP1','rP1') if survey=='ps1' else ('g','r')
        model = load_isochrone(data/'resources'/(PS1_MODEL if survey=='ps1' else cfg['isochrone']),bands=band)
        for arm,radii in ARMS.items():
            recipe = dict(prev['config'],coverage_subdivision=1,radii_arcmin=radii)
            path = DEST/arm/survey/'summary'/f'{name}-base'
            path.mkdir(exist_ok=True,parents=True)
            _,peaks,timing,_ = scan(sample,field,area,model,recipe)
            write_csv(path/'deduplicated_peaks.csv',peaks)
            if spec.get('truth'):
                write_csv(path/'recovery.csv',recovery(peaks,truth_table[spec['truth']],field,area,recipe,'base'))
            write_json(path/'manifest.json',dict(field=spec,config=recipe,status='complete',
                       area_deg2=prev['area_deg2'],depth='base',timer=timing,arm=arm,job=os.environ.get('SLURM_JOB_ID')))


def combine():
    summary, recovery_rows = [], []
    for arm in ARMS:
        for survey in SURVEYS:
            path=DEST/arm/survey
            finished={json.loads(m.read_text())['field']['id'] for m in (path/'summary').glob('*/manifest.json')}
            if finished!=set(IDS):
                raise ValueError(f'Missing scans in {arm} {survey}: {sorted(set(IDS)-finished)}')
            evaluate(path/'summary',path/'groups')
            summary.extend(dict(arm=arm,survey=survey,**r) for r in read_csv(path/'groups/sky_group_comparison.csv'))
            recovery_rows.extend(dict(arm=arm,survey=survey,**r) for r in read_csv(path/'groups/sky_group_recovery.csv'))
    write_csv(DEST/'compact_grid_comparison.csv',summary)
    write_csv(DEST/'compact_grid_recovery.csv',recovery_rows)


def inject(name):
    _,data,cfg = settings()
    cohort = yaml.safe_load(config_path('matched.yaml').read_text())
    spec = next(s for s in cohort['fields'] if s['id']==name and s['role']=='pilot_dev')
    field = finer_field(spec,cohort)
    version = 'v3' if name in ('fresh_01','fresh_03') else 'v4'
    raw = data/'runs'/version/'matched'/'ls_base'/name
    sample = np.load(raw/'sample.npy',allow_pickle=False)
    area = np.load(raw/'coverage.npy',allow_pickle=False)
    model = load_isochrone(data/'resources'/cfg['isochrone'])
    template = DEST/'fine_base/ls_base/summary'/f'{name}-base'
    recipe = json.loads((template/'manifest.json').read_text())['config']
    seed = [cfg['seed'],int(spec['ra']*1000),25]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    conditions = [(50,.25,22),(50,.35,36),(100,.25,36),(100,.35,22)]
    sites = choose_sites(field,area,recipe,len(conditions),rng)
    tree = cKDTree(sample[:,:2])
    calibration = [r for r in read_csv(DEST/'compact_grid_comparison.csv') if r['survey']=='ls_base']
    rows = []
    for j,(site,(distance,rh,n)) in enumerate(zip(sites,conditions)):
        new,truth = inject_one(site,distance,rh,n,rng,field,area,recipe,sample,model,tree)
        ra,dec = field.sky(*site)
        truth.update(ra_deg=ra,dec_deg=dec,D_kpc=distance,theta_h_arcmin=rh)
        for r in calibration:
            arm,cut = r['arm'],float(r['cutoff'])
            arm_cfg = dict(recipe,radii_arcmin=ARMS[arm])
            prev = DEST/arm/'ls_base/summary'/f'{name}-base/deduplicated_peaks.csv'
            blank = [dict({k:float(p[k]) for k in ('x','y','ra_deg','dec_deg','dm','rh_arcmin','score')},
                          channel='A_base',ranking=float(p['score'])) for p in read_csv(prev)
                     if float(p['score'])>=cut and p['method']=='A' and p['branch']=='main']
            _,peaks,seconds,_ = scan(np.vstack([sample,new]),field,area,model,arm_cfg)
            candidates = [dict(p,channel='A_base',ranking=p['score']) for p in peaks
                          if p['score']>=cut and p['method']=='A' and p['branch']=='main']
            rows.append(dict(field=name,trial=j,arm=arm,cutoff=cut,scan=seconds,**truth,
                             blank_spatial=matches(groups(blank),truth,cut,arm_cfg)['spatial'],
                             **matches(groups(candidates),truth,cut,arm_cfg)))
    write_csv(DEST/f'{name}-compact_injections.csv',rows)
    write_json(DEST/f'{name}-compact_injections.json',dict(seed=seed,mask_version=version,
                   job=os.environ.get('SLURM_JOB_ID'),experiment='isolated conditional LS catalog injections'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('field',choices=(*IDS,'combine'))
    p.add_argument('--archive',type=Path,default=Path('../holdout-v4/results/matched'))
    p.add_argument('--inject',action='store_true')
    a=p.parse_args()
    if a.field=='combine':
        combine()
    elif a.inject:
        inject(a.field)
    else:
        experiment(a.field,a.archive)
