"""Compact LS depth sensitivity in two new real backgrounds and one weak reference."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field, load_bricks, sample_pixels, select
from .group_budget import groups, matches
from .inject import choose_sites, inject_one
from .run import config_path, field_cache, read_csv, recovery, settings, sha, write_csv, write_json
from .search import load_isochrone, scan


def evaluate_catalog(sample,field,area,model,cfg,cut):
    _,peaks,timing,_=scan(sample,field,area,model,cfg)
    eligible=[dict(p,channel='A_base',ranking=p['score']) for p in peaks
              if p['branch']=='main' and p['method']=='A' and p['score']>=cut]
    return groups(eligible),timing


def run(name):
    plan=yaml.safe_load(config_path('depth_followup.yaml').read_text())
    root,data,cfg=settings()
    prior=Path(os.environ['LS_SAT_V5'])
    weak=name==plan['weak_reference']
    if weak:
        spec=plan['weak_field']
    elif name in plan['background_fields']:
        contents=list(prior.glob(f'batches/*/results/summary/{name}-base/manifest.json'))
        spec=json.loads(contents[0].read_text())['field']
    else:
        raise ValueError('Field is outside the registered depth controls')
    old,sources,mask,_=field_cache(root,data,spec,cfg,load_bricks(root) if weak else None)
    field=Field(old.ra,old.dec,plan['test_width_deg'],old.step,buffer=plan['test_buffer_arcmin'])
    sx,sy=field.xy(sources['RA'],sources['DEC'])
    sources=sources[(abs(sx)<field.limit)&(abs(sy)<field.limit)]
    cell=field.step/cfg['coverage_subdivision']
    axis=(np.arange(field.n*cfg['coverage_subdivision'])+.5)*cell-field.limit
    area=mask[sample_pixels(old,mask,*np.meshgrid(axis,axis))]
    cfg.update(methods=['A'],radii_arcmin=[.5,1,2,4],dm=[16.5,20.75,.25])
    config={'ls_base':cfg,'ls_deep':dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5)}
    archived=prior.parent/'holdout-v4/results/matched'
    cut={}
    for k in config:
        table=json.loads((archived/k/'groups/sky_group_policy.json').read_text())
        cut[k]=next(float(r['cutoff']) for r in table['thresholds'] if r['budget']==.3)
    sample={}
    used={}
    for k,recipe in config.items():
        sample[k],_,_,_,used[k]=select(sources,field,area,recipe)
    model=load_isochrone(data/'resources'/cfg['isochrone'])
    baseline={k:evaluate_catalog(s,field,area,model,config[k],cut[k])[0] for k,s in sample.items()}
    rows=[]
    if weak:
        ref=next(r for r in read_csv(Path('references/benchmarks.csv')) if r['name']==name)
        truth=dict(ra_deg=float(ref['ra_deg']),dec_deg=float(ref['dec_deg']),
                   D_kpc=float(ref['D_kpc']),theta_h_arcmin=float(ref['theta_h_arcmin']))
        x,y=field.xy(truth['ra_deg'],truth['dec_deg'])
        area_check=recovery([],dict(ref),field,area,cfg,'base')[0]
        for k,recipe in config.items():
            obj=sample[k]
            centre=np.hypot(obj[:,0]-x,obj[:,1]-y)<2
            psf=sources[used[k]][centre]
            rows.append(dict(field=name,arm=k,cutoff=cut[k],N_psf_within_2arcmin=len(psf),
                             forced_psf=int(((psf['FITBITS']&1)!=0).sum()),
                             covered=area_check['covered'],
                             core_valid_fraction=area_check['core_valid_fraction'],
                             off_valid_fraction=area_check['off_valid_fraction'],
                             **matches(baseline[k],truth,cut[k],recipe)))
    else:
        rng=np.random.default_rng(np.random.SeedSequence([plan['seed'],int(old.ra*1000)]))
        sites=choose_sites(field,area,cfg,len(plan['conditions']),rng)
        tree=cKDTree(sample['ls_deep'][:,:2])
        for j,(site,(distance,rh_pc,n)) in enumerate(zip(sites,plan['conditions'])):
            rh=np.degrees(np.arctan(rh_pc/(1000*distance)))*60
            new,t=inject_one(site,distance,rh,n,rng,field,area,config['ls_deep'],sample['ls_deep'],model,tree)
            ra,dec=field.sky(*site)
            truth=dict(ra_deg=ra,dec_deg=dec,D_kpc=distance,theta_h_arcmin=rh)
            for k,recipe in config.items():
                add=new[(new[:,2:4]<=[recipe['g_max'],recipe['r_max']]).all(1)]
                found,timing=evaluate_catalog(np.vstack([sample[k],add]),field,area,model,recipe,cut[k])
                rows.append(dict(field=name,trial=j,arm=k,N_used=len(add),N_generated=n,rh_pc=rh_pc,
                                 D_kpc=distance,cutoff=cut[k],
                                 blank_spatial=matches(baseline[k],truth,cut[k],recipe)['spatial'],
                                 **matches(found,truth,cut[k],recipe)))
    output=Path('results/verification')
    output.mkdir(exist_ok=True,parents=True)
    write_csv(output/f'depth_{name}.csv',rows)
    write_json(output/f'depth_{name}.json',dict(job=os.environ.get('SLURM_JOB_ID'),cutoffs=cut,
               config_sha256=sha(config_path('depth_followup.yaml')),weak=weak))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    run(p.parse_args().field)
