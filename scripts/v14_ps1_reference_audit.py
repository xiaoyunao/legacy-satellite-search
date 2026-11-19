"""Measure PS1-response sensitivity to LS reference shape, colour and local sky."""
import hashlib
import os
from pathlib import Path

import numpy as np
import yaml

from ls_satsearch.data import load_bricks, select
from ls_satsearch.matched import joint_coverage, ps1_measurements, reddening
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from scripts.v13_image_trials import match_to
from scripts.v14_ps1_response import stage_masks
from scripts.v12_selection_stats import interval


def run():
    directory=Path('configs/v13/matched/south').resolve()
    os.environ['LS_SAT_CONFIG_DIR']=str(directory)
    root,data,cfg=settings();plan=yaml.safe_load((directory/'matched.yaml').read_text())
    out=Path('results/v14/repeat_full/ps1_reference_audit');out.mkdir(parents=True,exist_ok=True)
    rows=[];inputs=[]
    edges=[0,20,21,22,22.5,23,23.5,24,30];colors=[-np.inf,.4,.8,np.inf]
    for site in read_csv(Path('configs/v14_repeat/image_fields.csv')):
        spec=next(r for r in plan['fields'] if r['id']==site['background'])
        expanded=dict(spec,width=plan['width_deg'],buffer_arcmin=plan['buffer_arcmin'])
        field,src,ls_area,provenance=field_cache(root,data,expanded,cfg,load_bricks(root,'south'))
        area=joint_coverage(field,ls_area,data/'resources/ps1/ps1d_mask_v2.1.fits')
        proxy_cfg=dict(cfg,g_max=24.5,r_max=24.,min_snr=10)
        _,_,valid,mags,selected=select(src,field,area,proxy_cfg)
        ordinary=(src['MASKBITS']&((1<<13)|(1<<17)))==0
        if 'FITBITS' in src.dtype.names:ordinary &= (src['FITBITS']&1)==0
        x,y=field.xy(src['RA'],src['DEC']);cx,cy=field.xy(float(site['ra_deg']),float(site['dec_deg']))
        nearby=np.hypot(x-cx,y-cy)<=20
        take=valid&ordinary&nearby
        src=src[take];mags=mags[take];point=selected[take]
        raw,manifest=ps1_measurements(spec,plan,data/'resources/ps1/tiles-v3'/site['background'])
        raw=raw[np.isfinite(raw[:,:2]).all(axis=1)&(raw[:,0]>=0)&(raw[:,0]<360)&(abs(raw[:,1])<=90)]
        link=match_to(np.column_stack([src['RA'],src['DEC']]),raw[:,:2],.7,field)
        found=link>=0;ps1=raw[np.maximum(link,0)]
        ps1_cfg=dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5)
        masks=stage_masks(ps1,reddening(ps1[:,0],ps1[:,1]),ps1_cfg)
        masks={k:v&found for k,v in masks.items()};masks['primary']=found
        variants={'ordinary_psf':point,'nonpsf_control':~point}
        needed=[k+'_'+b for k in ('FRACFLUX','FRACMASKED','FRACIN','RCHISQ') for b in 'GR']
        if set(needed)<=set(src.dtype.names):
            tight=point.copy()
            for b in 'GR':
                tight &= ((src['FRACFLUX_'+b]<.1)&(src['FRACMASKED_'+b]<.05)
                          &(src['FRACIN_'+b]>.9)&(src['RCHISQ_'+b]<2))
            variants['psf_tight_shape']=tight
        if 'REF_CAT' in src.dtype.names:
            variants['psf_gaia_reference_label']=point&np.char.startswith(np.char.strip(src['REF_CAT'].astype(str)),'G')
        held=np.array([int(hashlib.sha256(f'{r["RELEASE"]}:{r["BRICKID"]}:{r["OBJID"]}:487219'.encode()).hexdigest()[:8],16)%2
                       for r in src],dtype=bool)
        for split,fold in (('train',~held),('heldout',held)):
            for variant,subset in variants.items():
                for lo,hi in zip(edges,edges[1:]):
                    for cl,ch in zip(colors,colors[1:]):
                        use=fold&subset&(mags[:,0]>=lo)&(mags[:,0]<hi)&(mags[:,0]-mags[:,1]>=cl)&(mags[:,0]-mags[:,1]<ch)
                        n=int(use.sum());counts={k:int((use&v).sum()) for k,v in masks.items()}
                        bounds=interval(counts['selected'],n) if n else (None,None)
                        rows.append(dict(site=site['field'],split=split,reference_variant=variant,
                            g_lo=lo,g_hi=hi,color_lo=cl if np.isfinite(cl) else None,color_hi=ch if np.isfinite(ch) else None,
                            references=n,**counts,p_selected=counts['selected']/n if n else None,
                            interval_lo=bounds[0],interval_hi=bounds[1],supported=n>=20))
        inputs.append(dict(site=site['field'],ls_inputs=provenance,optional_shape_columns_present=set(needed)<=set(src.dtype.names),
            ps1_manifest_sha256=sha(data/'resources/ps1/tiles-v3'/site['background']/'manifest.json')))
    write_csv(out/'reference_stage_counts.csv',rows)
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),reference_radius_arcmin=20,
        inputs=inputs,code_sha256=sha(Path(__file__)),
        scope='Real PS1 selection on matched local LS references, with source-ID train/held-out split unchanged. Tight-shape and Gaia-reference labels are sensitivity/anchor strata, not independent truth labels; non-PSF sources can contain misclassified stars. The measured differences do not identify faint LS contamination or validate a truth-level PS1 probability. Colour/magnitude and field strata retain empty bins and intervals. Joint final selection includes PS1 gr/i/morphology/cuts once; never multiply by those stages again. No physical gain or completeness inference.'))


if __name__=='__main__':run()
