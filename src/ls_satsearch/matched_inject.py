"""Observe common latent stellar populations in the matched catalog samples."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .data import sample_pixels
from .group_budget import groups, matches
from .inject import choose_sites, match_trial, observe
from .matched import DEST, PS1_MODEL, SURVEYS, reddening
from .ps1_tiles import design
from .run import config_path, read_csv, runs_path, settings, sha, write_csv, write_json
from .search import binomial_tail_score, exact_onoff, load_isochrone, scan
from . import selection_response as sr

import yaml


def decomposition(raw, peaks, cmd, background, delivered, field, area, xy, distance, rh, cfg):
    dm = 5*np.log10(distance)+10
    trial = dict(x=xy[0],y=xy[1],dm=dm,rh_arcmin=rh)
    chosen,_ = cmd.weights(dm)
    sample = np.vstack([background,delivered])
    ni,no,ai,ao = exact_onoff(field,*xy,rh,cKDTree(sample[:,:2]),area,chosen)
    nb,nbo,_,_ = exact_onoff(field,*xy,rh,cKDTree(background[:,:2]),area,chosen[:len(background)])
    raw_match = match_trial(sorted(raw,key=lambda p:-p['score']),trial,'A',cfg) or {}
    dedup_match = match_trial(peaks,trial,'A',cfg) or {}
    ordered = groups([dict(p,channel='A_base',ranking=p['score']) for p in peaks if p['branch']=='main'])
    near = next(((i,a) for i,(a,_) in enumerate(ordered,1)
                 if np.hypot(a['x']-xy[0],a['y']-xy[1])<=max(cfg['match_min_arcmin'],rh)), (None,{}))
    return dict(N_injected_cmd=int(chosen[len(background):].sum()), N_added_on=ni-nb, N_added_off=no-nbo,
                N_on=ni,N_off=no,blank_on=nb,blank_off=nbo,area_on_arcmin2=ai,area_off_arcmin2=ao,
                expected_background_on=nbo*ai/ao if ao else None,
                fixed_aperture_score=binomial_tail_score(ni,ni+no,ai/(ai+ao)) if ai and ao else None,
                raw_score=raw_match.get('score'),dedup_score=dedup_match.get('score'),
                group_rank=near[0],group_score=near[1].get('score'),group_dm=near[1].get('dm'))


def run(field_id, archive=DEST, run_version=None):
    _,data_root,cfg = settings()
    matched = yaml.safe_load(config_path('matched.yaml').read_text())
    spec = next(s for s in matched['fields'] if s['id']==field_id and s['role']=='pilot_dev')
    field,_ = design(spec,matched)
    models = {}
    samples = {}
    manifests = {}
    cuts = {}
    paths = [data_root/'resources'/model for model in (cfg['isochrone'], PS1_MODEL)]
    # Pin the physical row correspondence before sharing IMF/phase draws across systems.
    signatures = [np.loadtxt(p,usecols=(0,1,2,3,4,5,6,7,14,15)) for p in paths]
    if not np.array_equal(*signatures):
        raise ValueError('PARSEC physical rows are not identical between catalogs')
    ls_model = load_isochrone(paths[0])
    prior = run_version is not None
    for survey in SURVEYS:
        work = (data_root/'runs'/run_version if prior else runs_path(data_root))/'matched'/survey/field_id
        samples[survey] = np.load(work/'sample.npy',allow_pickle=False)
        coverage = np.load(work/'coverage.npy',allow_pickle=False)
        if survey == 'ls_base':
            area = coverage
        if not np.array_equal(coverage,area):
            raise ValueError('Surveys do not share the same pixel mask')
        models[survey] = load_isochrone(paths[1],bands=('gP1','rP1')) if survey=='ps1' else ls_model
        name = archive/survey/'summary'/f'{field_id}-base'
        manifests[survey] = json.loads((name/'manifest.json').read_text())
        policy = json.loads((archive/survey/'groups/sky_group_policy.json').read_text())
        cuts[survey] = next(row['cutoff'] for row in policy['thresholds'] if row['policy']=='A_base')
        if cuts[survey] is None:
            raise ValueError('The shared review budget has no calibrated cutoff')
    trees = {survey:cKDTree(sample[:,:2]) for survey,sample in samples.items()}
    seed = [cfg['seed'],int(spec['ra']*1000),34]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    positions = choose_sites(field,area,cfg,2,rng)
    trials, curves = [], []
    if prior:
        archived_trials = {(r['trial'],r['survey']):r for r in
                           read_csv(archive/'injections'/f'{field_id}.csv')}
        ls_pool,ps_pool,response,response_rows = sr.models(
            field,area,spec,matched,manifests['ps1']['config'])
        with paths[1].open() as f:
            header = next(line[1:].split() for line in f if line.startswith('#') and 'iP1' in line)
        model_i = np.loadtxt(paths[1],usecols=header.index('iP1'))
    for index,(pos,(distance,stars)) in enumerate(zip(positions,[(50,28),(100,40)])):
        rh = np.degrees(np.arctan(.03/distance))*60
        dm = 5*np.log10(distance)+10
        # Define a common parent conditional LF from the union of the faint windows.
        included = np.zeros(len(ls_model[0]),dtype=bool)
        for survey,model in models.items():
            c = manifests[survey]['config']
            included |= np.all(model[0]+dm <= np.array([c['g_max'],c['r_max']])+.4,axis=1)
        weights = ls_model[1]*included
        drawn = rng.choice(len(weights),stars,p=weights/weights.sum())
        q = rng.uniform(0,.9,stars)
        angle = rng.uniform(0,2*np.pi,stars)
        xy = pos + rh*np.sqrt(q/(1-q))[:,None]*np.column_stack([np.cos(angle),np.sin(angle)])
        in_area = area[sample_pixels(field,area,*xy.T)]
        ra,dec = field.sky(*pos)
        truth = dict(ra_deg=ra,dec_deg=dec,theta_h_arcmin=rh,D_kpc=distance)
        ls_obs = observe(ls_model[0][drawn]+dm,pos,rng,manifests['ls_deep']['config'],
                         samples['ls_deep'],trees['ls_deep'])
        for survey in SURVEYS:
            c = manifests[survey]['config']
            if survey == 'ps1':
                phot,sig,selected = observe(models[survey][0][drawn]+dm,pos,rng,c,samples[survey],trees[survey])
            else:
                phot,sig,selected = ls_obs
                selected = selected & np.all(phot <= [c['g_max'],c['r_max']],axis=1)
            delivered = np.column_stack([xy,phot,sig])[selected & in_area]
            blank_path = archive/survey/'summary'/f'{field_id}-base/deduplicated_peaks.csv'
            blank = [{k:float(r[k]) for k in ('x','y','dm','rh_arcmin','ra_deg','dec_deg','score')}
                     for r in read_csv(blank_path) if r['method']=='A' and r['branch']=='main'
                     and float(r['score'])>=cuts[survey]]
            variants = [('v3_replay' if prior else 'conditional_gr', phot,sig,selected,{})]
            if prior:
                expected = archived_trials[str(index),survey]
                if len(delivered)!=int(expected['N_used']):
                    raise ValueError(f'Cannot reproduce v3 member count for {field_id} {index} {survey}')
                noise_seed = np.random.default_rng(np.random.SeedSequence(
                    [*seed,index,1 if survey=='ps1' else 2]))
                pool = ps_pool if survey=='ps1' else ls_pool
                intrinsic = models[survey][0][drawn]+dm
                if survey=='ps1':
                    injected_ra,injected_dec = field.sky(*xy.T)
                    intrinsic = np.column_stack([intrinsic,model_i[drawn]+dm+
                                                 1.682*reddening(injected_ra,injected_dec)])
                measured,err = sr.perturb(intrinsic,pool,pos,noise_seed)
                if survey=='ps1':
                    accept,stage = sr.ps1_select(measured,err,c,response,noise_seed)
                else:
                    accept = sr.gr_accept(measured,err,c)
                    stage = dict(N_gr=int(accept.sum()))
                variants.append(('preselection_response',measured[:,:2],err[:,:2],accept,stage))
                goal = np.array([21.,22.,22.5,23.,23.5,24.])
                near = np.atleast_1d(pool[3].query(pos,k=min(len(pool[0]),2400))[1])
                old_near = np.atleast_1d(trees[survey].query(pos,k=min(len(samples[survey]),1800))[1])
                for b,band in enumerate('gr'):
                    raw_sig = sr.measurement_curve(pool[1][near,b],pool[2][near,b],goal)
                    used_sig = sr.measurement_curve(samples[survey][old_near,b+2],
                                                    samples[survey][old_near,b+4],goal)
                    curves.extend(dict(field=field_id,trial=index,survey=survey,band=band,
                                       magnitude=m,raw_sigma=a,selected_sigma=z)
                                  for m,a,z in zip(goal,raw_sig,used_sig))
            for variant,values,errors,use,stage in variants:
                delivered = np.column_stack([xy,values,errors])[use & in_area]
                raw,peaks,timing,cmd = scan(np.vstack([samples[survey],delivered]),field,area,models[survey],c)
                scanned = [r for r in peaks if r['score']>=cuts[survey]]
                blank_match,injected_match = (matches(groups([dict(p,channel='A_base',ranking=p['score'])
                              for p in choices]),truth,cuts[survey],c) for choices in (blank,scanned))
                details = decomposition(raw,peaks,cmd,samples[survey],delivered,field,area,pos,distance,rh,c) if prior else {}
                if prior and variant=='v3_replay' and str(injected_match['spatial'])!=expected['spatial']:
                    raise ValueError(f'Cannot reproduce v3 spatial recovery for {field_id} {index} {survey}')
                trials.append(dict(field=field_id,trial=index,survey=survey,variant=variant,D_kpc=distance,rh_pc=30,
                                   N_generated=stars,N_after_selection=int(use.sum()),
                                   N_in_valid_area=int(in_area.sum()),N_used=len(delivered),
                                   blank_spatial=blank_match['spatial'],cutoff=cuts[survey],
                                   seconds=sum(timing.values()),**injected_match,**stage,**details))
    dest = DEST/'injections'
    dest.mkdir(exist_ok=True,parents=True)
    write_csv(dest/f'{field_id}.csv',trials)
    write_json(dest/f'{field_id}.json',dict(status='complete',seed=seed,job=os.environ.get('SLURM_JOB_ID'),
               model_sha256=[sha(p) for p in paths],
               selection=('PS1 empirical i validity, i S/N and PSF-Kron response on LS bright PSF proxies. '
                          'LS TYPE=PSF conditional. Unsupported PS1 bins assume unity and are counted.'
                          if prior else 'Conditional catalog injection. Morphology/measurement completeness is unmodeled.')))
    if prior:
        write_csv(dest/f'{field_id}-noise.csv',curves)
        write_csv(dest/f'{field_id}-ps1-response.csv',response_rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field')
    parser.add_argument('--archive',type=Path,default=DEST)
    parser.add_argument('--run-version')
    args = parser.parse_args()
    run(args.field,args.archive,args.run_version)
