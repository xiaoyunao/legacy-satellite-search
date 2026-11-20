"""Render held full-science context from verified saved C, without refitting.

Only private real-data pilot output is produced by the CLI. Identity/score-bearing
context belongs to phase two, after user grades are sealed, not the anonymous ZIP.
"""
import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from ls_satsearch.data import load_bricks,select
from ls_satsearch.plots import candidate
from ls_satsearch.review import convert_peak,image_cutouts,observing_page
from ls_satsearch.run import field_cache,read_csv,settings,sha,write_json
from ls_satsearch.search import load_isochrone
from scripts.v14_review_integrity import mode_table,verify


def render_mode(dest,mode,seed,membership,raw_path,field,area,sample,sources,valid,
                mags,chosen,model,spec,conditions,root,region,bricks):
    dest.mkdir(parents=True,exist_ok=False)
    checksum=sha(membership)
    with np.load(membership,allow_pickle=False) as saved:
        ids=saved['source_ids'];prob=saved['probability']
        integrity=verify(mode,ids,prob)
    selected_ids=sources[['RELEASE','BRICKID','OBJID']][chosen]
    lookup={tuple(k):i for i,k in enumerate(selected_ids)}
    if not {tuple(k) for k in ids}<=lookup.keys():raise ValueError('Saved sources do not belong to this selection')
    idx=np.array([lookup[tuple(k)] for k in ids],dtype=int)
    peak=convert_peak(dict(seed,method=seed['channel'].split('_')[0],rank=int(float(mode['rank'])),branch='main'))
    peak.update(ra_deg=float(mode['fit_ra_deg']),dec_deg=float(mode['fit_dec_deg']),
                dm=float(mode['fit_dm']),rh_arcmin=float(mode['fit_rh_arcmin']))
    peak['x'],peak['y']=field.xy(peak['ra_deg'],peak['dec_deg'])
    # Stream only nearby template peaks; do not materialize a full-field CSV/tree.
    raw=[]
    with raw_path.open() as stream:
        for row in csv.DictReader(stream):
            if row['method']==peak['method'] and np.hypot(float(row['x'])-peak['x'],float(row['y'])-peak['y'])<peak['rh_arcmin']:
                raw.append(convert_peak(row))
    candidate(dest/'context.png',spec,field,area,sample,sources,valid,mags,chosen,peak,idx,prob,raw,model,conditions)
    environment=observing_page(dest/'conditions.png',root,bricks,sources,valid,field,peak,
                               dict(field_id=spec['id']))
    images=image_cutouts(dest/'images.png',root,bricks,field,peak,sample[idx,:2],prob,details=True,region=region)
    if sha(membership)!=checksum:raise ValueError('Saved C changed during rendering')
    write_json(dest/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),mode=mode,
        original_discovery_seed=seed,membership_sha256=checksum,membership_integrity=integrity,
        renderer_sha256=sha(Path(__file__)),plot_renderer_sha256=sha(Path('src/ls_satsearch/plots.py')),
        image_renderer_sha256=sha(Path('src/ls_satsearch/review.py')),
        raw_template_peaks_path=str(raw_path),nearby_template_peaks=len(raw),
        environment=environment,**images,
        outputs={p.name:sha(p) for p in dest.glob('*.png')},refitted=False,
        scope='Held phase-two score/identity/contribution context. Saved local counts, richness and TS verified algebraically; no likelihood optimization, source reassignment or new C result. Same-exposure methods are not independent confirmation. Local TS is not global significance. Not a human grade or final release.'))


def pilot(case_id):
    base=Path('results/v14/shortlist');case=next(r for r in read_csv(base/'cases.csv') if r['case_id']==case_id)
    table,modes=mode_table(case)
    config=Path('configs/v14/cohorts')/case['cohort'];os.environ['LS_SAT_CONFIG_DIR']=str(config)
    root,data,cfg=settings();region=cfg.get('region','south')
    manifest=Path(f'regional_v14_{case["cohort"]}/results/summary/{case["field"]}-base/manifest.json')
    saved=json.loads(manifest.read_text());model_path=data/'resources'/cfg['isochrone']
    if saved['config']!=cfg or saved['model_sha256']!=sha(model_path):raise ValueError('Original selection/template differs')
    bricks=load_bricks(root,region)
    field,sources,area,_=field_cache(root,data,saved['field'],cfg,bricks)
    sample,_,valid,mags,chosen=select(sources,field,area,cfg)
    model=load_isochrone(model_path)
    seeds=read_csv(base/f'input_modes_{case["cohort"]}.csv')
    frozen=Path('results/v14/human_review/membership_integrity.json');proof=json.loads(frozen.read_text())
    if sha(frozen.with_suffix('.csv'))!=proof['csv_sha256']:raise ValueError('Frozen integrity proof changed')
    snapshots={(r['case_id'],int(r['seed_rank'])):r for r in read_csv(frozen.with_suffix('.csv'))}
    out=Path('results/v14/human_review/final_private/context_renderer_pilot')/case_id
    if out.exists():raise ValueError('Preserve previous private pilot')
    for i,mode in enumerate(sorted(modes,key=lambda m:(float(m['fit_dm']),float(m['fit_rh_arcmin'])))):
        rank=int(float(mode['rank']));snapshot=snapshots[(case_id,rank)]
        membership=data/snapshot['frozen_path']
        if sha(membership)!=snapshot['membership_sha256']:raise ValueError('Frozen membership changed')
        seed=next(r for r in seeds if r['group_id']==case['source_group_id'] and int(float(r['peak_rank']))==rank)
        raw=data/'runs/v14'/f'{case["field"]}-base/all_template_peaks.csv'
        render_mode(out/f'alternative_{i+1:02d}',mode,seed,membership,raw,field,area,sample,sources,
            valid,mags,chosen,model,saved['field'],saved['observing_conditions_source_sample'],root,region,bricks)
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),mode_table_sha256=sha(table),
        scan_manifest_sha256=sha(manifest),modes=len(modes),refitted=False,final_review_release=False,
        scope='Private previously exposed old-case saved-context pilot. Full final sample, required evidence, sampling and PDF/privacy/page QA remain gates. Original75 untouched.'))
    print(dict(saved_modes_rendered=len(modes),refitted=False,private_pilot=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True)
    pilot(p.parse_args().case)
