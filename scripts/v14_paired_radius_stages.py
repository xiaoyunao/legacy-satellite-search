"""Measure paired native stages without re-extracting any image."""
import os
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import joint_coverage
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from ls_satsearch.search import CMD, load_isochrone
from scripts import v13_image_trials as native
from scripts.v14_paired_radius import prepare, VERSION, CONFIG, OUT


def stage_measurements(indices, label):
    prepare();root,data,_=settings();cfg=yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text());plan=yaml.safe_load(Path('configs/v13/matched/south/matched.yaml').read_text())
    cfg.update(dm=plan['dm'],radii_arcmin=plan['radii_arcmin'],methods=['A'],review_budgets_deg2=plan['review_budgets_deg2'])
    model=load_isochrone(native.template_paths(data,cfg)[0]);sites={r['field']:r for r in read_csv(CONFIG/'image_fields.csv')}
    references=read_csv(Path('results/v14/repeat_full/full_summary.csv'));tasks=read_csv(CONFIG/'tasks.csv');records=[];inputs={str(OUT/'registration.json'):sha(OUT/'registration.json')}
    for index in indices:
        row=tasks[index];site=sites[row['site']];name=site['field'];trial=int(row['new_trial']);parent=int(row['original_trial']);local=native.local_coordinates(site)
        spec=next(r for r in plan['fields'] if r['id']==site['background']);spec=dict(spec,width=plan['width_deg'],buffer_arcmin=plan['buffer_arcmin'])
        field,_,ls_area,_=field_cache(root,data,spec,cfg,load_bricks(root,'south'));area=joint_coverage(field,ls_area,data/'resources/ps1/ps1d_mask_v2.1.fits')
        blank_folder=data/'image-v14_repeat'/name/'blank';blank,blank_cat=native.native_table(blank_folder);blank_sky=np.column_stack([blank['RA'],blank['DEC']]);blank_initial=np.load(blank_folder/'initial_detection.npy',allow_pickle=False)
        proof=OUT/'native_validation'/f'{name}-trial{trial:02d}.json'
        saved=json.loads(proof.read_text())
        for p,digest in saved['inputs'].items():
            if sha(Path(p))!=digest:raise ValueError('Native proof changed')
        inputs[str(proof)]=sha(proof)
        for arm in ('ls_base','ls_deep'):
            actual=cfg.copy()
            if arm=='ls_deep':
                for band in 'gr':actual[band+'_max']+=.5
            measured={}
            for variant,stage in [('parent10',data/'image-v14_repeat'/name/f'trial{parent:02d}'),('paired3',data/('image-'+VERSION)/name/f'trial{trial:02d}')]:
                truth=np.load(stage/'truth.npy',allow_pickle=False);sample,cat=native.native_table(stage);sky=np.column_stack([sample['RA'],sample['DEC']]);pos=np.column_stack([truth['ra'],truth['dec']])
                obs=(np.load(stage/'injected_exposures.npy',allow_pickle=False)[:,:2]>0).all(axis=1);obs &= area[sample_pixels(field,area,*field.xy(*pos.T))]
                initial=np.load(stage/'initial_detection.npy',allow_pickle=False);new_initial=native.match_to(initial,blank_initial,.8,local)<0;first=native.match_to(pos,initial[new_initial],.8,local)>=0
                novel=native.match_to(sky,blank_sky,.8,local)<0;found=native.match_to(pos,sky[novel],.8,local);linked=np.where(found>=0,np.flatnonzero(novel)[np.maximum(found,0)],-1) if novel.any() else found
                psf,selected=native.photometry(sample,linked,field,area,actual);selected_sample,_,_,_,chosen=select(sample,field,area,actual)
                cmd=np.zeros(len(sample),bool);cmd[chosen]=CMD.top_hat(selected_sample[:,2:4],selected_sample[:,4:6],20,model[2]);on_cmd=(linked>=0)&cmd[np.maximum(linked,0)]
                light=10**(-.4*(truth['g0']-.59*(truth['g0']-truth['r0'])-.01-20))
                counts=dict(N_rendered=len(truth),N_exposed=int(obs.sum()),N_initial=int((obs&first).sum()),N_final=int((obs&(linked>=0)).sum()),N_psf=int((obs&psf).sum()),N_used=int((obs&selected).sum()),N_cmd=int((obs&on_cmd).sum()),L_rendered=float(light.sum()),L_exposed=float(light[obs].sum()),L_PSF=float(light[obs&psf].sum()),L_hard=float(light[obs&selected].sum()))
                xy=np.column_stack(local.xy(*pos.T));neighbor=cKDTree(xy).query(xy,k=2)[0][:,1]*60
                counts['N_member_neighbor_lt0p8arcsec']=int((neighbor<.8).sum());counts['N_blank_neighbor_lt0p8arcsec']=int((cKDTree(np.column_stack(local.xy(*blank_sky.T))).query(xy)[0]*60<.8).sum())
                measured[variant]=counts
                for p in (stage/'truth.npy',stage/'injected_exposures.npy',stage/'initial_detection.npy',cat):inputs[str(p)]=sha(p)
            expected=next(r for r in references if r['site']==name and int(r['trial'])==parent and r['arm']==arm)
            if any(measured['parent10'][key]!=int(expected[key]) for key in ('N_rendered','N_exposed','N_final','N_psf','N_used')):raise ValueError('Accepted original stage counts do not reproduce')
            if measured['parent10']['L_rendered']!=measured['paired3']['L_rendered']:raise ValueError('Paired input light differs')
            record=dict(site=name,new_trial=trial,original_trial=parent,latent_population_id=parent,arm=arm,full_IMF_realized_MV_proxy=expected['realized_MV_proxy'])
            for variant,counts in measured.items():record.update({variant+'_'+key:value for key,value in counts.items()})
            records.append(record)
    if any(sha(Path(p))!=digest for p,digest in inputs.items()):raise ValueError('Measurement input changed')
    write_csv(OUT/(label+'_stage_pairs.csv'),records)
    write_json(OUT/(label+'_stage_acceptance.json'),dict(job=os.getenv('SLURM_JOB_ID'),native_cases=len(indices),paired_depth_cases=len(records),shared_populations=len({r['original_trial'] for r in records}),inputs=inputs,code_sha256=sha(Path(__file__)),original_stage_counts_reproduced=True,rendered_intrinsic_light_identical=True,blind_search_performed=False,scope='Same finite rendered populations, shrunk about the same true centre. Actual exposure, extraction/unique-association, classification and cuts are measured. Local extinction/coverage/foreground blending and changed photon-noise realization are part of the response; no pure mutual-crowding or full physical Pdet claim. PS1 response is not calibrated by this test.'))
    print('PAIRED_RADIUS_STAGE_ACCEPTED',label,len(records),flush=True)


