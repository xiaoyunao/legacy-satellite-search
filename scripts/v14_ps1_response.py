"""Measure actual PS1 selection stages on held-out, ordinary LS point-source proxies."""
from pathlib import Path
import argparse
import hashlib
import os

import numpy as np
import yaml

from ls_satsearch.data import Field, load_bricks, select
from ls_satsearch.matched import joint_coverage, ps1_measurements, reddening
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from scripts.v13_image_trials import match_to
from scripts.v12_selection_stats import interval


def stage_masks(rows, ebv, cfg):
    ra,dec,g,r,ge,re,i,kron,ie=rows.T
    limit=2.5/np.log(10)/cfg['min_snr']
    gr=(np.isfinite([ra,dec,g,r,ge,re]).all(axis=0)&(g>0)&(r>0)&(ge>0)&(re>0)&(ge<=limit)&(re<=limit))
    valid_i=gr&np.isfinite(i+ie)&(i>0)&(ie>0)
    i_snr=valid_i&(ie<=limit)
    shape=i_snr&np.isfinite(kron)&(kron>0)&(i-kron<.05)
    final=shape&np.isfinite(ebv)&(g-3.172*ebv<=cfg['g_max'])&(r-2.271*ebv<=cfg['r_max'])
    return dict(gr=gr,i_valid=valid_i,i_snr=i_snr,morphology=shape,selected=final)


def run(radius_arcmin=None):
    directory=Path('configs/v13/matched/south').resolve()
    os.environ['LS_SAT_CONFIG_DIR']=str(directory)
    root,data,cfg=settings(); matched=yaml.safe_load((directory/'matched.yaml').read_text())
    ps1_cfg=dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5)
    out=Path('results/v14/repeat')/('ps1_response_local' if radius_arcmin else 'ps1_response')
    out.mkdir(parents=True,exist_ok=True)
    rows=[];provenance=[]
    edges=[0,20,21,22,22.5,23,23.5,24,30];colors=[-np.inf,.4,.8,np.inf]
    for site in read_csv(Path('configs/v14_repeat/image_fields.csv')):
        field_id=site['background'];spec=next(r for r in matched['fields'] if r['id']==field_id)
        expanded=dict(spec,width=matched['width_deg'],buffer_arcmin=matched['buffer_arcmin'])
        field,sources,ls_area,inputs=field_cache(root,data,expanded,cfg,load_bricks(root,'south'))
        mask=joint_coverage(field,ls_area,data/'resources/ps1/ps1d_mask_v2.1.fits')
        proxy_cfg=dict(cfg,g_max=24.5,r_max=24.,min_snr=10)
        proxy,_,_,_,original=select(sources,field,mask,proxy_cfg)
        chosen=original.copy()
        if 'FITBITS' in sources.dtype.names:chosen &= (sources['FITBITS']&1)==0
        chosen &= (sources['MASKBITS']&((1<<13)|(1<<17)))==0
        # Preserve the original selected row order after the ordinary-processing proxy cuts.
        proxy=proxy[chosen[original]]
        source=sources[chosen]
        if radius_arcmin is not None:
            center=np.array(field.xy(float(site['ra_deg']),float(site['dec_deg'])))
            nearby=np.linalg.norm(proxy[:,:2]-center,axis=1)<=radius_arcmin
            proxy,source=proxy[nearby],source[nearby]
        raw,manifest=ps1_measurements(spec,matched,data/'resources/ps1/tiles-v3'/field_id)
        sky=np.isfinite(raw[:,:2]).all(axis=1)&(raw[:,0]>=0)&(raw[:,0]<360)&(abs(raw[:,1])<=90)
        raw=raw[sky]
        if not len(raw) or not len(source):raise ValueError('No real reference or PS1 rows')
        linked=match_to(np.column_stack([source['RA'],source['DEC']]),raw[:,:2],.7,field)
        found=linked>=0
        ps1=raw[np.maximum(linked,0)]
        masks=stage_masks(ps1,reddening(ps1[:,0],ps1[:,1]),ps1_cfg)
        masks={k:v&found for k,v in masks.items()};masks['primary']=found
        held=np.array([int(hashlib.sha256(f'{r["RELEASE"]}:{r["BRICKID"]}:{r["OBJID"]}:487219'.encode()).hexdigest()[:8],16)%2
                       for r in source],dtype=bool)
        for split,selected in (('train',~held),('heldout',held)):
            for lo,hi in zip(edges,edges[1:]):
                for cl,ch in zip(colors,colors[1:]):
                    use=selected&(proxy[:,2]>=lo)&(proxy[:,2]<hi)&(proxy[:,2]-proxy[:,3]>=cl)&(proxy[:,2]-proxy[:,3]<ch)
                    n=int(use.sum());counts={k:int((use&v).sum()) for k,v in masks.items()}
                    low,high=interval(counts['selected'],n) if n else (None,None)
                    rows.append(dict(site=site['field'],split=split,ls_g_lo=lo,ls_g_hi=hi,
                        ls_color_lo=None if not np.isfinite(cl) else cl,ls_color_hi=None if not np.isfinite(ch) else ch,
                        references=n,**counts,p_selected_given_LS_proxy=counts['selected']/n if n else None,
                        interval_lo=low,interval_hi=high,response_supported=n>=20))
        provenance.append(dict(site=site['field'],references=len(source),ps1_primary_rows=len(raw),
            ls_inputs=inputs,ps1_manifest_sha256=sha(data/'resources/ps1/tiles-v3'/field_id/'manifest.json')))
    write_csv(out/'selection_stage_counts.csv',rows)
    training={(r['site'],r['ls_g_lo'],r['ls_color_lo']):r for r in rows if r['split']=='train'}
    comparisons=[]
    for test in (r for r in rows if r['split']=='heldout'):
        train=training[test['site'],test['ls_g_lo'],test['ls_color_lo']]
        supported=train['response_supported'] and test['response_supported']
        comparisons.append(dict(site=test['site'],ls_g_lo=test['ls_g_lo'],ls_g_hi=test['ls_g_hi'],
            ls_color_lo=test['ls_color_lo'],ls_color_hi=test['ls_color_hi'],train_n=train['references'],
            heldout_n=test['references'],supported=supported,train_prediction=train['p_selected_given_LS_proxy'],
            heldout_observed=test['p_selected_given_LS_proxy'],
            residual=test['p_selected_given_LS_proxy']-train['p_selected_given_LS_proxy'] if supported else None))
    write_csv(out/'heldout_response_residuals.csv',comparisons)
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),fields=provenance,
        ps1_cfg=ps1_cfg,reference_radius_arcmin=radius_arcmin,
        scope='Actual PS1 primary/gr/i/shape selection on ordinary LS SNR>=10 point-source proxies, split by source ID. This is conditional on the LS reference catalogue, not a truth-level PS1 completeness or an independent-background validation. Full-field diagnostics must not be assumed to calibrate the CCD stamp. Train and held-out bins require support before use. Joint final-selection rates must not be multiplied by photometric cuts a second time. No optimistic extrapolation or physical satellite gain is inferred.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--radius-arcmin',type=float)
    args=p.parse_args()
    if args.radius_arcmin is not None and args.radius_arcmin<=0:p.error('Radius must be positive')
    run(args.radius_arcmin)
