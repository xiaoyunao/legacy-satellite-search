"""Replay frozen production A on the same CCD catalogues, without re-extraction."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import monotonic

import numpy as np
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.group_budget import groups, matches
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone, scan

ROOT = Path('results/v14/repeat_full/production_replay')
POLICY = Path('results/v14/discovery/south_ps1/main/sky_group_policy.json')
SEARCH = Path('configs/v14/cohorts/south_ps1/search.yaml')
MATCHED = Path('configs/v13/matched/south/matched.yaml')


def blank_agreement(released, blank, field, area, cfg, splice, native):
    """Compare rerun and published records; neither catalogue is a truth label."""
    use=np.hypot(*field.xy(released['RA'],released['DEC']))<splice
    indices=np.flatnonzero(use)
    links=native.match_to(np.column_stack([released['RA'][use],released['DEC'][use]]),
        np.column_stack([blank['RA'],blank['DEC']]),.8,field)
    good=links>=0;take=np.maximum(links,0)
    _,_,pub_gr,pub_mag,pub_keep=select(released,field,area,cfg)
    _,_,new_gr,new_mag,new_keep=select(blank,field,area,cfg)
    rows=[]
    for label,faint in (('all',np.ones(len(indices),bool)),('g0_ge22p5',pub_mag[indices,0]>=22.5)):
        valid=good&faint
        rows.append(dict(subset=label,published_sources=int(faint.sum()),position_matched=int(valid.sum()),
            published_selected=int((faint&pub_keep[indices]).sum()),
            selected_in_both=int((valid&pub_keep[indices]&new_keep[take]).sum()),
            published_selected_only=int((valid&pub_keep[indices]&~new_keep[take]).sum()),
            rerun_selected_only=int((valid&~pub_keep[indices]&new_keep[take]).sum()),
            published_selected_unmatched=int((faint&pub_keep[indices]&~good).sum())))
    offsets={}
    for k,band in enumerate('GR'):
        quality=good&pub_keep[indices]&new_keep[take]
        quality &= released['FLUX_'+band][indices]*np.sqrt(released['FLUX_IVAR_'+band][indices])>=20
        quality &= blank['FLUX_'+band][take]*np.sqrt(blank['FLUX_IVAR_'+band][take])>=20
        residual=new_mag[take,k]-pub_mag[indices,k]
        quality &= np.isfinite(residual)
        offsets[band]=dict(matched_high_SNR20_PSF_pairs=int(quality.sum()),
            rerun_minus_published_dereddened_mag_q16_q50_q84=np.quantile(residual[quality],[.16,.5,.84]).tolist() if quality.any() else None)
    return dict(selection_agreement=rows,photometry_offsets=offsets,
        scope='Unique0.8arcsec positional comparison inside the native splice circle on the same real data, not independent stellar truth or absolute detection completeness. Both catalogues use the frozen production gr/quality/PSF selection. Faint attrition remains separately visible; bright-pair flux agreement does not certify faint classifications.')


def prepare():
    cfg = yaml.safe_load(SEARCH.read_text())
    policy = json.loads(POLICY.read_text())
    cuts = [r['cutoff'] for r in policy['thresholds'] if r['policy']=='A_base' and r['budget']==.3]
    if len(cuts)!=1 or cuts[0] is None:
        raise ValueError('Require the original frozen South PS1 production cutoff')
    for key, value in {**policy['recipe'], **policy['limits']['base']}.items():
        if cfg.get(key) != value:
            raise ValueError('Production configuration differs from the saved policy: '+key)
    if cfg.get('main_dm_max',20.75)!=20.75 or cfg['radii_arcmin']!=[.5,1,2,4,8,16]:
        raise ValueError('Unexpected production distance/scale strategy')
    ROOT.mkdir(parents=True, exist_ok=True)
    registration = ROOT/'registration.json'
    saved = dict(configuration=cfg, cutoff=cuts[0], width_deg=1.8,
        buffer_arcmin=100, source_sha256={str(p):sha(p) for p in
            (SEARCH,POLICY,MATCHED,Path('configs/v14_repeat/protocol.yaml'),Path('configs/v14_repeat/image_fields.csv'))},
        code_sha256=sha(Path(__file__)), seed=487430,
        scope='Same144 native catalogues and true populations, baseline only, complete ordinary A distance grid and all six production scales/cut. Scans the entire valid control core without truth priors; matching is afterward. Buffer100arcmin exceeds the96arcmin largest on/off radius. Uses LS+official PS1-assigned census mask, without an extra requirement for PS1 catalogue availability. These are control fields, not newly discovered area or exact owned production-tile/edge sampling. Old matched-budget measurements and their C fits remain separate; C is not rerun or borrowed here. Generation/stamp limits and physical PS1 response validation remain unresolved.')
    if registration.exists():
        if json.loads(registration.read_text())!=saved:raise ValueError('Production replay registration changed')
    else:write_json(registration,saved)
    print('REGISTERED_PRODUCTION_REPLAY',cuts[0],flush=True)


def load_registration():
    path=ROOT/'registration.json';saved=json.loads(path.read_text())
    if saved['code_sha256']!=sha(Path(__file__)):raise ValueError('Replay implementation changed after registration')
    for name,checksum in saved['source_sha256'].items():
        if sha(Path(name))!=checksum:raise ValueError('Registered production source changed: '+name)
    return path,saved


def run(name, trials=None):
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Run replay on an allocated CPU node')
    os.environ['LS_SAT_IMAGE_VERSION']='v14_repeat'
    from scripts import v13_image_trials as native
    if native.VERSION!='v14_repeat':raise ValueError('Unexpected physical source namespace')
    accepted=Path('results/v14/repeat_full/full_acceptance.json')
    proof=json.loads(accepted.read_text())
    if not proof.get('all_native_and_LS_measurements_accepted'):
        raise ValueError('Finish the original frozen144 measurements before policy replay')
    if sha(Path('results/v14/repeat_full/full_summary.csv'))!=proof['summary_sha256']:
        raise ValueError('Accepted matched-budget comparison changed')
    registration,saved=load_registration();started=monotonic()
    root,data,_=settings();cfg=saved['configuration'];cut=saved['cutoff']
    site,plan,_=native.context(name)
    old=[r for r in read_csv(Path('results/v14/repeat_full/full_summary.csv')) if r['site']==name and r['arm']=='ls_base']
    if len(old)!=48:raise ValueError('Incomplete matched-budget comparison')
    old={int(r['trial']):r for r in old}
    matched=yaml.safe_load(MATCHED.read_text())
    spec=next(r for r in matched['fields'] if r['id']==site['background'])
    spec=dict(spec,width=saved['width_deg'],buffer_arcmin=saved['buffer_arcmin'],role='injection_control')
    field,released,area,inputs=field_cache(root,data,spec,cfg,load_bricks(root,'south'))
    storage=data/'image-v14_repeat'/name
    blank,blank_cat=native.native_table(storage/'blank')
    blank_sky=np.column_stack([blank['RA'],blank['DEC']])
    splice=plan['splice_radius_arcmin'];radius=plan['matching_radius_arcsec']
    blank_check=blank_agreement(released,blank,field,area,cfg,splice,native)
    model=load_isochrone(native.template_paths(data,cfg)[0])
    exterior=select(released,field,area,cfg)[0]
    clean=select(blank,field,area,cfg)[0]
    identity=hashlib.sha256(exterior.tobytes()+area.tobytes()).hexdigest()
    background=native.replaced(field,site,exterior,clean,splice)
    _,blank_peaks,_,_=scan(background,field,area,model,cfg)
    blank_groups=groups([dict(r,channel='A_base',ranking=r['score']) for r in blank_peaks if r['branch']=='main'])
    rows=[];sources={str(accepted):sha(accepted),str(registration):sha(registration),str(blank_cat):sha(blank_cat)}
    indices=list(range(48)) if trials is None else sorted(set(trials))
    if not indices or any(i<0 or i>=48 for i in indices):raise ValueError('Invalid frozen trial IDs')
    cache=ROOT/name/'trials';cache.mkdir(parents=True,exist_ok=True)
    for trial in indices:
        stage=storage/f'trial{trial:02d}'
        source=Path('results/v14/repeat/validation')/(name+f'-trial{trial:02d}.json')
        validated=json.loads(source.read_text());native_cat,cat=native.native_table(stage)
        if not validated['native_products_validated'] or sha(cat)!=validated['tractor_sha256'] or sha(stage/'truth.npy')!=validated['truth_sha256']:
            raise ValueError('Registered native catalogue or population changed')
        cache_inputs=dict(registration=sha(registration),accepted=sha(accepted),
            catalogue=validated['tractor_sha256'],truth=validated['truth_sha256'],
            blank=sha(blank_cat),exterior_and_mask=identity)
        cached=cache/f'{trial:02d}.json'
        sources[str(source)]=sha(source);sources[str(cat)]=sha(cat);sources[str(stage/'truth.npy')]=sha(stage/'truth.npy')
        if cached.is_file():
            prior=json.loads(cached.read_text())
            if prior['input_sha256']!=cache_inputs:raise ValueError('Cached trial belongs to different detector/data')
            rows.append(prior['row']);print('VERIFIED_REPLAY_CACHE',name,trial,flush=True);continue
        truth=json.loads((stage/'truth.json').read_text());stars=np.load(stage/'truth.npy',allow_pickle=False)
        injected=np.column_stack([stars['ra'],stars['dec']])
        observed=(np.load(stage/'injected_exposures.npy',allow_pickle=False)[:,:2]>0).all(axis=1)
        observed &= area[sample_pixels(field,area,*field.xy(*injected.T))]
        final_sky=np.column_stack([native_cat['RA'],native_cat['DEC']])
        novel=native.match_to(final_sky,blank_sky,radius,field)<0
        found=native.match_to(injected,final_sky[novel],radius,field)
        linked=np.where(found>=0,np.flatnonzero(novel)[np.maximum(found,0)],-1) if novel.any() else found
        _,selected=native.photometry(native_cat,linked,field,area,cfg)
        after=native.replaced(field,site,exterior,select(native_cat,field,area,cfg)[0],splice)
        products=data/'runs/v14/production_replay'/name/f'trial{trial:02d}'
        print('PRODUCTION_POLICY_REPLAY',name,trial,flush=True)
        result=native.blind(after,field,area,model,cfg,truth,cut,followup=False,diagnostics=True,products=products)
        previous=old[trial]
        row=dict(site=name,trial=trial,arm='production_ls_base',D_kpc=truth['D_kpc'],
            rh_pc=truth['rh_pc'],target_MV_proxy=truth['expected_MV_proxy'],realized_MV_proxy=truth['realized_MV_proxy'],
            latent_population_id=trial,realization_id=trial//6,N_exposed=int(observed.sum()),N_used=int((observed&selected).sum()),
            matched_N_exposed=int(previous['N_exposed']),matched_N_used=int(previous['N_used']),
            matched_spatial=previous['spatial'],matched_correct_mode_exists=previous['correct_mode_exists'],
            matched_blind_correct=previous['blind_correct'],matched_correct_mode_in_any_spatial_group=previous['correct_mode_in_any_spatial_group'],
            blank_spatial=matches(blank_groups,truth,cut,cfg)['spatial'],
            C_state='not_run_for_production_replay_do_not_reuse_matched_C',**result)
        rows.append(row)
        write_json(cached,dict(row=row,input_sha256=cache_inputs))
    write_csv(ROOT/(name+'.csv'),rows)
    write_json(ROOT/(name+'.json'),dict(job=os.environ['SLURM_JOB_ID'],site=name,rows=len(rows),
        expected_trials=48,requested_trials=indices,complete_registered_site=indices==list(range(48)),
        seconds=monotonic()-started,input_sha256=sources,field=spec,real_mask_inputs=inputs,
        blank_release_comparison=blank_check,
        blank_qualifying_sky_groups=sum(anchor['ranking']>=cut for anchor,_ in blank_groups),
        source_code_sha256={str(p):sha(p) for p in (Path(__file__),Path('src/ls_satsearch/search.py'),Path('src/ls_satsearch/group_budget.py'))},
        scope=saved['scope']))
    print('PRODUCTION_POLICY_SITE_COMPLETE',name,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run'));p.add_argument('--field')
    p.add_argument('--trials',type=int,nargs='+')
    args=p.parse_args();prepare() if args.mode=='prepare' else run(args.field,args.trials)
