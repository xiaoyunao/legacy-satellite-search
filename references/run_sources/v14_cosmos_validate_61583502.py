"""Test LS proxy purity and PS1 source response against independent COSMOS references."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import joint_coverage, ps1_measurements, reddening
from ls_satsearch.run import coverage_metrics, field_cache, settings, sha, write_csv, write_json
from scripts.v13_image_trials import match_to
from scripts.v14_ps1_response import stage_masks
from scripts.v14_repeat_statistics import interval

CONFIG=Path('configs/v14_cosmos_reference')
OUT=Path('results/v14/repeat_full/cosmos_reference')


def response(coords,raw,field,ps1_cfg,radius):
    linked=match_to(coords,raw[:,:2],radius,field);found=linked>=0
    sample=raw[np.maximum(linked,0)]
    events={k:v&found for k,v in stage_masks(sample,reddening(sample[:,0],sample[:,1]),ps1_cfg).items()}
    return linked,dict(primary=found,**events)


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Read real reference/survey catalogues on a compute node')
    protocol=Path('configs/v14_repeat/cosmos_reference.yaml')
    spec=yaml.safe_load(protocol.read_text());plan=yaml.safe_load((CONFIG/'validation.yaml').read_text())
    acquisition=OUT/'acquisition.json';acquired=json.loads(acquisition.read_text())
    parent=Path(acquired['subset_path'])
    if sha(protocol)!=acquired['config_sha256'] or sha(parent)!=acquired['subset_sha256']:
        raise ValueError('Independent reference acquisition changed')
    reference=np.load(parent,allow_pickle=False)
    if len(np.unique(reference['ID']))!=len(reference):raise ValueError('Duplicate independent reference identifiers')
    os.environ['LS_SAT_CONFIG_DIR']=str(CONFIG.resolve())
    root,data,cfg=settings();matched=yaml.safe_load((CONFIG/'matched.yaml').read_text())
    field_spec=matched['fields'][0];field_name=field_spec['id']
    expanded=dict(field_spec,width=matched['width_deg'],buffer_arcmin=matched['buffer_arcmin'])
    field,sources,ls_area,ls_inputs=field_cache(root,data,expanded,cfg,load_bricks(root,'south'))
    area=joint_coverage(field,ls_area,data/'resources/ps1/ps1d_mask_v2.1.fits')
    ps1_directory=data/'resources/ps1/tiles-v3'/field_name
    raw,ps1_manifest=ps1_measurements(field_spec,matched,ps1_directory)
    raw=raw[np.isfinite(raw[:,:2]).all(axis=1)&(raw[:,0]>=0)&(raw[:,0]<360)&(abs(raw[:,1])<=90)]
    if not len(raw):raise ValueError('No valid actual PS1 primary catalogue')
    ps1_policy=Path(plan['PS1_policy_manifest'])
    ps1_cfg=json.loads(ps1_policy.read_text())['ps1_cfg']
    inputs=[protocol,CONFIG/'validation.yaml',CONFIG/'matched.yaml',CONFIG/'search.yaml',acquisition,
        parent,ps1_directory/'manifest.json',ps1_policy]
    input_hashes={str(p):sha(p) for p in inputs}
    code_hashes={str(p):sha(p) for p in (Path(__file__),Path('src/ls_satsearch/data.py'),
        Path('src/ls_satsearch/matched.py'),Path('src/ls_satsearch/ps1_tiles.py'),Path('scripts/v14_ps1_response.py'))}
    ref_sky=np.column_stack([reference['RA'],reference['DEC']]);ls_sky=np.column_stack([sources['RA'],sources['DEC']])
    rx,ry=field.xy(*ref_sky.T)
    ref_area=(abs(rx)<field.width*30)&(abs(ry)<field.width*30)&area[sample_pixels(field,area,rx,ry)]
    quality=ref_area&(reference['FLAG_HSC']==0)&reference['HSC_G_VALID'].astype(bool)&reference['HSC_R_VALID'].astype(bool)
    for band in ('G','R'):
        flux,error=reference['HSC_'+band+'_FLUX'],reference['HSC_'+band+'_FLUXERR']
        quality &= np.isfinite(flux+error)&(error>0)&(flux>0)&(flux/error>=spec['quoted_HSC_gr_min_flux_SNR'])
    star=quality&(reference['ACS_MU_CLASS']==2)&(reference['LP_TYPE']==1)
    galaxy=quality&(reference['ACS_MU_CLASS']==1)&(reference['LP_TYPE']==0)
    color=reference['HSC_G_MAG']-reference['HSC_R_MAG'];blue=(color>=spec['reference_blue_observed_HSC_gr'][0])&(color<spec['reference_blue_observed_HSC_gr'][1])
    ls_to_ref=match_to(ls_sky,ref_sky,plan['match_radius_arcsec'],field)
    linked=ls_to_ref>=0;ref_to_ls=np.full(len(reference),-1,dtype=int)
    ref_to_ls[ls_to_ref[linked]]=np.flatnonzero(linked)
    ref_found=ref_to_ls>=0
    def split(key):return int(hashlib.sha256(f'{key}:{spec["source_ID_holdout_seed"]}'.encode()).hexdigest()[:8],16)%2
    ref_keys=['COSMOS:'+str(value) for value in reference['ID']]
    ref_fold=np.array([split(key) for key in ref_keys])
    ls_fold=np.array([split(ref_keys[j] if j>=0 else f'LS:{r["RELEASE"]}:{r["BRICKID"]}:{r["OBJID"]}') for r,j in zip(sources,ls_to_ref)])
    if not np.array_equal(ls_fold[linked],ref_fold[ls_to_ref[linked]]):raise ValueError('Counterpart holdout leakage')
    _,base_flow,_,ls_mags,base_keep=select(sources,field,area,cfg)
    deep_cfg=dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5)
    deep_keep=select(sources,field,area,deep_cfg)[4]
    proxy_cfg=dict(cfg,g_max=24.5,r_max=24.,min_snr=10)
    proxy=select(sources,field,area,proxy_cfg)[4]
    if 'FITBITS' in sources.dtype.names:proxy &= (sources['FITBITS']&1)==0
    proxy &= (sources['MASKBITS']&((1<<13)|(1<<17)))==0
    psf=np.char.strip(sources['TYPE'].astype(str))=='PSF'
    ps1_ls,ls_events=response(ls_sky,raw,field,ps1_cfg,plan['match_radius_arcsec'])
    ps1_ref,ref_events=response(ref_sky,raw,field,ps1_cfg,plan['match_radius_arcsec'])
    for label,values in (('ls_catalogue_match',np.ones(len(sources),bool)),('ls_PSF_model',psf),('ls_base',base_keep),('ls_deep',deep_keep),('ls_proxy',proxy)):
        ref_events[label]=ref_found&values[np.maximum(ref_to_ls,0)]
    ref_points=np.column_stack([rx,ry]);tree=cKDTree(ref_points)
    neighbour=tree.query(ref_points,k=2)[0][:,1]*60
    ls_second=tree.query(np.column_stack(field.xy(*ls_sky.T)),k=2)[0][:,1]*60
    single=linked&(ls_second>=plan['match_radius_arcsec'])
    star_ls=single&star[np.maximum(ls_to_ref,0)];galaxy_ls=single&galaxy[np.maximum(ls_to_ref,0)]
    rows=[]
    for label,context in (('all',np.ones(len(reference),bool)),('reference_neighbour_ge2arcsec',neighbour>=plan['reference_neighbour_arcsec'])):
        for split_name,fold in (('train',0),('heldout',1)):
            for population,colors in (('all_colors',np.ones(len(reference),bool)),('blue_HSC_observed',blue)):
                for low,high in zip(plan['HSC_observed_g_edges'],plan['HSC_observed_g_edges'][1:]):
                    chosen=star&context&colors&(ref_fold==fold)&(reference['HSC_G_MAG']>=low)&(reference['HSC_G_MAG']<high)
                    n=int(chosen.sum());record=dict(context=label,split=split_name,population=population,HSC_observed_g_low=low,HSC_observed_g_high=high,references=n,supported=n>=spec['minimum_references_per_supported_bin'])
                    record.update({key:int((chosen&event).sum()) for key,event in ref_events.items()})
                    for key in ('ls_base','ls_deep','selected'):
                        low_ci,high_ci=interval(record[key],n) if n else (None,None)
                        record.update({key+'_joint_fraction':record[key]/n if n else None,key+'_reference_binomial_low':low_ci,key+'_reference_binomial_high':high_ci})
                    rows.append(record)
    composition=[];tests=[]
    ls_color=ls_mags[:,0]-ls_mags[:,1]
    for low,high in zip(plan['LS_proxy_g_edges'],plan['LS_proxy_g_edges'][1:]):
        for cl,ch in zip(plan['LS_proxy_color_edges'],plan['LS_proxy_color_edges'][1:]):
            cell=proxy&(ls_mags[:,0]>=low)&(ls_mags[:,0]<high)&(ls_color>=cl)&(ls_color<ch)
            summary={}
            for name,fold in (('train',0),('heldout',1)):
                use=cell&(ls_fold==fold);n=int(use.sum());ns=int((use&star_ls).sum());ng=int((use&galaxy_ls).sum())
                k=int((use&ls_events['selected']).sum());gold=use&star_ls;kg=int((gold&ls_events['selected']).sum())
                composition.append(dict(split=name,LS_g0_low=low,LS_g0_high=high,LS_gr0_low=cl,LS_gr0_high=ch,proxy_sources=n,
                    independent_stellar_references=ns,independent_resolved_SED_galaxies=ng,ambiguous_or_unmatched=n-ns-ng,
                    stellar_fraction_label_lower=ns/n if n else None,stellar_fraction_label_upper=1-ng/n if n else None,
                    PS1_selected=k,PS1_selected_stellar_references=kg))
                summary[name]=(n,k,ns,kg)
            n,k,ns,kg=summary['train'];_,_,nt,kt=summary['heldout']
            support=n>=spec['minimum_references_per_supported_bin'] and nt>=spec['minimum_references_per_supported_bin']
            tests.append(dict(LS_g0_low=low,LS_g0_high=high,LS_gr0_low=cl,LS_gr0_high=ch,train_proxy_n=n,train_stellar_n=ns,
                heldout_stellar_n=nt,supported=support,proxy_mixture_prediction=k/n if n else None,
                stellar_reference_prediction=kg/ns if ns else None,heldout_stellar_observed=kt/nt if nt else None,
                mixture_prediction_minus_heldout=k/n-kt/nt if support else None,
                stellar_prediction_minus_heldout=kg/ns-kt/nt if support and ns>=spec['minimum_references_per_supported_bin'] else None))
    write_csv(OUT/'independent_stellar_source_response.csv',rows)
    write_csv(OUT/'LS_proxy_reference_composition.csv',composition)
    write_csv(OUT/'heldout_estimator_validation.csv',tests)
    private=data/'runs/v14/cosmos_reference';private.mkdir(parents=True,exist_ok=True)
    pending=private/('joins-pending-'+os.environ['SLURM_JOB_ID']+'.npz')
    np.savez_compressed(pending,reference_ID=reference['ID'],ls_to_reference=ls_to_ref,reference_to_ls=ref_to_ls,
        reference_to_ps1=ps1_ref,ls_to_ps1=ps1_ls,reference_fold=ref_fold,ls_fold=ls_fold,
        stellar_reference=star,resolved_SED_galaxy=galaxy,ordinary_LS_proxy=proxy)
    digest=sha(pending);joined=private/('joins-'+digest+'.npz')
    if joined.exists():
        if sha(joined)!=digest:raise ValueError('Immutable reference join artifact changed')
        pending.unlink()
    else:pending.replace(joined)
    for name,digest in input_hashes.items():
        if sha(Path(name))!=digest:raise ValueError('Reference input changed during validation')
    effective,_=coverage_metrics(field,area,cfg)
    conditions={}
    sx,sy=field.xy(sources['RA'],sources['DEC'])
    source_area=area[sample_pixels(field,area,sx,sy)]
    for band in 'GR':
        measured=source_area&(sources['FLUX_'+band]>0)&(sources['FLUX_IVAR_'+band]>0)
        for column in ('PSFSIZE_'+band,'PSFDEPTH_'+band):
            if column not in sources.dtype.names:continue
            valid=measured&np.isfinite(sources[column])&(sources[column]>0)
            values=sources[column][valid]
            if column.startswith('PSFDEPTH'):values=22.5-2.5*np.log10(5/np.sqrt(values))
            conditions[column+('_observed_5sigma_mag' if column.startswith('PSFDEPTH') else '_arcsec')]=np.quantile(values,[.16,.5,.84]).tolist() if len(values) else None
    faint=blue&(reference['HSC_G_MAG']>=spec['reference_faint_observed_HSC_g'][0])&(reference['HSC_G_MAG']<spec['reference_faint_observed_HSC_g'][1])
    write_json(OUT/'validation.json',dict(job=os.environ['SLURM_JOB_ID'],input_sha256=input_hashes,code_sha256=sha(Path(__file__)),
        reference_rows=len(reference),common_mask_reference_positions=int(ref_area.sum()),quality_reference_positions=int(quality.sum()),
        morphology_SED_stellar_references=int(star.sum()),blue_faint_stellar_references=int((star&faint).sum()),
        blue_faint_heldout_stellar_references=int((star&faint&(ref_fold==1)).sum()),
        ordinary_LS_proxies=int(proxy.sum()),supported_heldout_comparison_bins=sum(r['supported'] for r in tests),
        common_reference_control_deg2=effective,LS_inputs=ls_inputs,LS_base_cutflow=base_flow,
        source_sampled_conditions=conditions,source_code_sha256=code_hashes,
        private_joins=dict(path=str(joined),sha256=sha(joined)),physical_PS1_transfer_validated=False,
        scope=plan['scope']+' Morphology/SED agreement is an independent reference, not perfect truth. IR detection selection, incomplete/ambiguous matches, epoch/proper-motion effects, native HSC bandpasses and quoted uncorrected errors remain explicit limitations. Holdout separates matched counterpart IDs in one sky; close blends and common image/background correlations remain. Conditions are source-sampled, not uniform-sky completeness depths. The selected column is PS1 DR2 joint selection. Intermediate counts share the full reference denominator; do not multiply joint losses again.'))
    print('INDEPENDENT_REFERENCE_VALIDATION',int(star.sum()),int((star&faint).sum()),int(proxy.sum()),flush=True)


if __name__=='__main__':run()
