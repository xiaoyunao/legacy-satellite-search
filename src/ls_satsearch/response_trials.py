"""Matched latent-population trials with shared random draws in both selection arms."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import yaml

from .data import sample_pixels
from .group_budget import groups,matches
from .inject import choose_sites
from .matched import PS1_MODEL,SURVEYS,reddening
from .ps1_tiles import design
from .run import config_path,read_csv,settings,write_csv,write_json
from .search import load_isochrone,scan
from . import selection_response as sr


def get_rate(values,response):
    mag,color,bins = response
    x = np.searchsorted(mag,values[:,0],side='right')-1
    y = np.searchsorted(color,values[:,0]-values[:,1],side='right')-1
    rates = [bins.get((i,j)) for i,j in zip(x,y)]
    return np.array([1. if r is None else r for r in rates]),np.array([r is None for r in rates])


def audit_errors(field_id,pool,point):
    rows=[]
    for band in range(2):
        mags,err=pool[1][:,band],pool[2][:,band]
        for center in (21.5,22.,22.5,23.,23.5,24.):
            for type_,group in [('point',point),('extended',~point)]:
                v=(abs(mags-center)<.25)&np.isfinite(err)&(err>0)&group
                rows.append(dict(field=field_id,band='gr'[band],bin_center=center,morphology=type_,
                                 measured=int(v.sum()),sigma_p50=float(np.median(err[v])) if v.any() else None))
    return rows


def run(field_id,version,archive,physical_plan=None,output=None):
    _,data,cfg=settings()
    matched=yaml.safe_load(config_path('matched.yaml').read_text())
    spec=next(s for s in matched['fields'] if s['id']==field_id and s['role']=='pilot_dev')
    field,_=design(spec,matched)
    samples,configs,cuts,empty={}, {}, {}, {}
    masks=[]
    for survey in SURVEYS:
        work=data/'runs'/version/'matched'/survey/field_id
        samples[survey]=np.load(work/'sample.npy',allow_pickle=False)
        masks.append(np.load(work/'coverage.npy',allow_pickle=False))
        summary=archive/survey/'summary'/f'{field_id}-base'
        configs[survey]=json.loads((summary/'manifest.json').read_text())['config']
        policy=json.loads((archive/survey/'groups/sky_group_policy.json').read_text())
        cuts[survey]=next(r['cutoff'] for r in policy['thresholds'] if r['budget']==.3)
        blank=[dict({k:float(r[k]) for k in ('x','y','ra_deg','dec_deg','rh_arcmin','dm','score')},
                   channel='A_base',ranking=float(r['score']))
               for r in read_csv(summary/'deduplicated_peaks.csv') if
               r['branch']=='main' and r['method']=='A' and float(r['score'])>=cuts[survey]]
        empty[survey]=groups(blank)
    if not all(np.array_equal(masks[0],m) for m in masks[1:]):
        raise ValueError('Matched sample masks differ')
    area=masks[0]
    ls,_,ps1_response,ps1_bins,ls_point,ps1_point,ls_response,ls_bins,is_point=sr.models(
        field,area,spec,matched,configs['ps1'],ls_config=configs['ls_deep'])
    paths=[data/'resources'/cfg['isochrone'],data/'resources'/PS1_MODEL]
    signatures=[np.loadtxt(p,usecols=(0,1,2,3,4,5,6,7,14,15)) for p in paths]
    if not np.array_equal(*signatures):
        raise ValueError('PARSEC population rows differ')
    model_ls=load_isochrone(paths[0])
    model_ps1=load_isochrone(paths[1],bands=('gP1','rP1'))
    with paths[1].open() as f:
        headers=next(line[1:].split() for line in f if line.startswith('#') and 'iP1' in line)
    model_i=np.loadtxt(paths[1],usecols=headers.index('iP1'))
    physical = yaml.safe_load(physical_plan.read_text()) if physical_plan else None
    seed=[cfg['seed'],int(spec['ra']*1000),physical['seed'] if physical else 55]
    rng=np.random.default_rng(np.random.SeedSequence(seed))
    conditions = physical['conditions'] if physical else [(50,10,28),(100,15,40)]*3
    positions=choose_sites(field,area,cfg,len(conditions),rng)
    if physical and len(positions)!=len(conditions):
        raise ValueError('Physical pilot is missing eligible injection sites')
    # The archived native templates lack Johnson V. Use a fixed SDSS-like
    # colour transformation as a luminosity proxy for the entire IMF.
    g_abs,r_abs=model_ls[0].T
    v_proxy=g_abs-.59*(g_abs-r_abs)-.01
    v_flux=10**(-.4*v_proxy)
    trials=[]
    for trial,(pos,(distance,size,normalization)) in enumerate(zip(positions,conditions)):
        dm=5*np.log10(distance)+10
        rh=np.degrees(np.arctan(size/(1000*distance)))*60
        margin=.8 if physical else .4
        valid_model=np.any([np.all(model[0]+dm<=[c['g_max']+margin,c['r_max']+margin],axis=1)
                            for model,c in ((model_ls,configs['ls_deep']),(model_ps1,configs['ps1']))],axis=0)
        weights=model_ls[1]*valid_model
        if physical:
            total_lum=10**(-.4*normalization)
            expected=weights.sum()*total_lum/np.dot(model_ls[1],v_flux)
            n=rng.poisson(expected)
        else:
            n=normalization
        draw=rng.choice(len(weights),n,p=weights/weights.sum())
        q=rng.uniform(0,1 if physical else .9,n); t=rng.uniform(0,2*np.pi,n)
        xy=pos+rh*np.sqrt(q/(1-q))[:,None]*np.column_stack([np.cos(t),np.sin(t)])
        in_area=area[sample_pixels(field,area,*xy.T)]&np.all(np.abs(xy)<field.limit,axis=1)
        ra,dec=field.sky(*xy.T)
        truth_ra,truth_dec=field.sky(*pos)
        truth=dict(ra_deg=truth_ra,dec_deg=truth_dec,D_kpc=distance,theta_h_arcmin=rh)
        noise=rng.normal(size=(n,3))
        uniforms=rng.random((2,n))
        ls_obs=sr.perturb(model_ls[0][draw]+dm,ls_point,pos,rng,standard_noise=noise[:,:2])
        for survey in SURVEYS:
            c=configs[survey]
            if physical:
                c=dict(c,dm=[16.5,20.75,c['dm'][2]])
            if survey=='ps1':
                intrinsic=np.column_stack([model_ps1[0][draw]+dm,model_i[draw]+dm+1.682*reddening(ra,dec)])
                phot,err=sr.perturb(intrinsic,ps1_point,pos,rng,standard_noise=noise)
                grade,counts=sr.ps1_select(phot,err,c,ps1_response,rng,uniforms=uniforms)
                model=model_ps1
            else:
                phot,err=ls_obs
                rates,unknown=get_rate(phot,ls_response)
                usable=sr.gr_accept(phot,err,c)
                grade=usable&(uniforms[1]<rates)
                counts=dict(N_gr=int(usable.sum()),N_response_unsupported=int((unknown&usable).sum()))
                model=model_ls
            g,r=phot[:,:2],err[:,:2]
            conditional=sr.gr_accept(g,r,c)
            last_selection,last=None,None
            arms=[('both_proxy_response',grade)] if physical else [('conditional_gr',conditional),('both_proxy_response',grade)]
            for label,sel in arms:
                index=sel&in_area
                blank=matches(empty[survey],truth,cuts[survey],c)
                if last is None or not np.array_equal(index,last_selection):
                    delivered=np.column_stack([xy,g,r])[index]
                    if physical and len(delivered)==0:
                        last=blank
                    else:
                        _,peaks,_,_=scan(np.vstack([samples[survey],delivered]),field,area,model,c)
                        eligible=[dict(p,channel='A_base',ranking=p['score']) for p in peaks if
                                  p['score']>=cuts[survey] and (not physical or p['branch']=='main')]
                        last=matches(groups(eligible),truth,cuts[survey],c)
                last_selection=index
                trials.append(dict(field=field_id,trial=trial,survey=survey,arm=label,
                                   D_kpc=distance,rh_pc=size,N_latent=n,N_in_valid_area=int(in_area.sum()),
                                   N_used=int(index.sum()),
                                   blank_spatial=blank['spatial'],cutoff=cuts[survey],
                                   **(dict(expected_MV_proxy=normalization,N_expected_near_limits=expected) if physical else {}),
                                   **counts,**last))
    out=output or Path('results/v9/physical_trials' if physical else 'results/matched_response')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/f'{field_id}.csv',trials)
    write_csv(out/f'{field_id}-ls-response.csv',ls_bins)
    write_csv(out/f'{field_id}-ps1-response.csv',ps1_bins)
    write_csv(out/f'{field_id}-ls-error-by-type.csv',audit_errors(field_id,ls,is_point))
    write_json(out/f'{field_id}.json',dict(status='complete',job=os.environ.get('SLURM_JOB_ID'),seed=seed,
               model='Common latent rows and sky positions, common standardized gr noise and morphology draws. '
               'Proxy shape response conditional on observed counterpart; unsupported bins use unity. '
               'Catalog entry and image completeness are unmeasured.',
               **(dict(physical_plan=physical,search_dm_branch='main',luminosity_definition='expected IMF-integrated V proxy, '
                       'V=g-0.59(g-r)-0.01 in DECam AB; truncated injection draws near either sample limit')
                  if physical else {})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    p.add_argument('--version',choices=('v3','v4'),required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--physical-plan',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    run(a.field,a.version,a.archive,a.physical_plan,a.output)
