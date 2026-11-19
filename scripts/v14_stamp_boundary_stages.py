"""Separate added outer members from changed old-member selection in the real guard."""
import json
import os
from pathlib import Path

import numpy as np
import yaml

from ls_satsearch.data import load_bricks, sample_pixels
from ls_satsearch.matched import joint_coverage
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from scripts import v13_image_trials as native


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Inspect raw native products on a compute node')
    out=Path('results/v14/stamp_boundary');acceptance=out/'acceptance.json'
    accepted=json.loads(acceptance.read_text())
    for name,digest in accepted['input_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Accepted boundary input changed')
    root,data,_=settings();cfg=yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    plan=yaml.safe_load(Path('configs/v13/matched/south/matched.yaml').read_text())
    cfg.update(dm=plan['dm'],radii_arcmin=plan['radii_arcmin'],methods=['A'],review_budgets_deg2=plan['review_budgets_deg2'])
    rows=[]
    for site in read_csv(Path('configs/v14_stamp_boundary/image_fields.csv')):
        name=site['field'];local=native.local_coordinates(site)
        spec=next(r for r in plan['fields'] if r['id']==site['background'])
        spec=dict(spec,width=plan['width_deg'],buffer_arcmin=plan['buffer_arcmin'])
        field,_,ls_area,_=field_cache(root,data,spec,cfg,load_bricks(root,'south'))
        area=joint_coverage(field,ls_area,data/'resources/ps1/ps1d_mask_v2.1.fits')
        storage=data/'image-v14_stamp_boundary'/name
        blank,_=native.native_table(storage/'blank');blank_sky=np.column_stack([blank['RA'],blank['DEC']])
        core=np.load(storage/'trial01/truth.npy',allow_pickle=False)
        reference=read_csv(Path('results/v14_stamp_boundary/image_response')/(name+'-blind.csv'))
        for arm in ('ls_base','ls_deep'):
            actual=cfg.copy()
            if arm=='ls_deep':
                for band in 'gr':actual[band+'_max']+=.5
            variants={}
            for trial in (1,0):
                stage=storage/f'trial{trial:02d}';truth=np.load(stage/'truth.npy',allow_pickle=False)
                if not np.array_equal(truth[:len(core)],core):raise ValueError('Original stars changed')
                sample,_=native.native_table(stage);sky=np.column_stack([sample['RA'],sample['DEC']])
                novel=native.match_to(sky,blank_sky,.8,local)<0
                found=native.match_to(np.column_stack([truth['ra'],truth['dec']]),sky[novel],.8,local)
                linked=np.where(found>=0,np.flatnonzero(novel)[np.maximum(found,0)],-1) if novel.any() else found
                psf,selected=native.photometry(sample,linked,field,area,actual)
                obs=(np.load(stage/'injected_exposures.npy',allow_pickle=False)[:,:2]>0).all(axis=1)
                obs &= area[sample_pixels(field,area,*field.xy(truth['ra'],truth['dec']))]
                selected &= obs;psf &= obs
                expected=next(r for r in reference if r['arm']==arm and int(r['trial'])==trial)
                if int(selected.sum())!=int(expected['N_used']):raise ValueError('Selected counts do not reproduce')
                light=10**(-.4*(truth['g0']-.59*(truth['g0']-truth['r0'])-.01-20))
                variants[trial]=dict(selected=selected,psf=psf,light=light,observed=obs)
                rows.append(dict(site=name,arm=arm,variant='extended' if trial==0 else 'original',
                    N_rendered=len(truth),N_original=len(core),N_added=len(truth)-len(core),
                    original_selected=int(selected[:len(core)].sum()),added_selected=int(selected[len(core):].sum()),
                    original_PSF=int(psf[:len(core)].sum()),added_PSF=int(psf[len(core):].sum()),
                    true_light_proxy_rendered=float(light.sum()),true_light_proxy_exposed=float(light[obs].sum()),
                    true_light_proxy_selected=float(light[selected].sum())))
            old=variants[1]['selected'];new=variants[0]['selected'][:len(core)]
            rows[-1].update(old_selected_retained=int((old&new).sum()),old_selected_lost=int((old&~new).sum()),
                old_members_newly_selected=int((~old&new).sum()))
    write_csv(out/'member_origin_stage_comparison.csv',rows)
    write_json(out/'member_origin_stage_acceptance.json',dict(job=os.environ['SLURM_JOB_ID'],
        acceptance_sha256=sha(acceptance),code_sha256=sha(Path(__file__)),selected_counts_reproduced=True,
        scope='Aggregate member-origin/true V-proxy diagnostics on accepted real native catalogues; no blind scan rerun or member rows exported. Original-member changes can combine fit interactions and changed photon-noise realization; one targeted draw does not isolate a population-level systematic truncation bias.'))
    print('BOUNDARY_MEMBER_ORIGIN_STAGES_ACCEPTED',len(rows),flush=True)


if __name__=='__main__':run()
