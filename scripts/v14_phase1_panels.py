"""Unweighted, score-hidden evidence; pilot outputs remain private, not a release.

The rendering function is separate from discovery/C and never changes a fit.
The CLI uses one previously exposed frozen case to check real data rendering.
Final sample selection, all-mode coverage and PDF/ZIP QA remain separate gates.
"""
import argparse
from functools import cache
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.data import load_bricks, select
from ls_satsearch.review import coadd_stamp
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_json
from ls_satsearch.search import load_isochrone

image_digest=cache(sha)

def render(output, label, sample, area, field, model, mode, root, region, bricks):
    """No probabilities, contributor order, scores or identities enter panels."""
    x,y=field.xy(float(mode['fit_ra_deg']),float(mode['fit_dec_deg']))
    rh=float(mode['fit_rh_arcmin']);dm=float(mode['fit_dm'])
    delta=sample[:,:2]-(x,y);radius=np.linalg.norm(delta,axis=1)
    outer=np.sqrt(3.5**2+1.5**2)
    core=radius<=1.5*rh;off=(radius>3.5*rh)&(radius<=outer*rh)
    near=radius<=6*rh
    fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
    ax=axes[0,0]
    ax.scatter(*delta[near].T,s=8,color='#647c89')
    for scale,style in ((1,'-'),(1.5,'--'),(3.5,':'),(outer,':')):
        ax.add_patch(plt.Circle((0,0),scale*rh,fill=False,color='#555555',lw=.7,linestyle=style))
    ax.set(xlabel='East (arcmin)',ylabel='North (arcmin)',title='Observed selected sources',
           xlim=(-6*rh,6*rh),ylim=(-6*rh,6*rh),aspect='equal')
    for ax,use,title in ((axes[0,1],core,'Core CMD'),(axes[0,2],off,'Background CMD')):
        g,r,eg,er=sample[use,2:6].T
        ax.errorbar(g-r,g,xerr=np.hypot(eg,er),yerr=eg,fmt='.',ms=3,lw=.45,
                    alpha=.55,color='#647c89')
        ax.plot(model[:,0]-model[:,1],model[:,0]+dm,'.',ms=1.2,color='#b64b40')
        ax.set(xlabel='(g-r)0 (mag)',ylabel='g0 (mag)',title=f'{title}\n{use.sum():,} sources'+(' (equal geometric area)' if title=='Background CMD' else ''),
               xlim=(-.5,1.8),ylim=(max(24.5,g.max(initial=24.5)),15))
    bx,by=field.xy(bricks['RA'],bricks['DEC'])
    image_status={}
    halfwidth=min(270.,max(30.,2*rh*60))
    for band,ax in zip('gr',axes[1,:2]):
        distances=np.hypot(bx-x,by-y)
        paths=[]
        for i in np.flatnonzero(distances<18)[np.argsort(distances[distances<18])]:
            name=bricks['BRICKNAME'][i].strip()
            path=root/region/'coadd'/name[:3]/name/f'legacysurvey-{name}-image-{band}.fits.fz'
            if path.is_file():paths.append(path)
        stamp,extent=coadd_stamp(paths,field,x,y,halfwidth,.524)
        finite=np.isfinite(stamp);lo,hi=np.nanpercentile(stamp,(8,99.5)) if finite.any() else (0,1)
        ax.imshow(stamp,origin='lower',extent=extent,cmap='gray',vmin=lo,vmax=hi)
        ax.plot(0,0,'+',color='#ffbb50',ms=7)
        ax.set(title=f'Observed {band} coadd',xlabel='East (arcsec)',ylabel='North (arcsec)')
        image_status[band]=dict(finite_pixel_fraction=float(finite.mean()),
                                image_inputs_sha256={str(p):image_digest(p) for p in paths})
    step=2*field.limit/len(area)
    axis=(np.arange(len(area))+.5)*step-field.limit
    ix=np.flatnonzero(abs(axis-x)<=6*rh);iy=np.flatnonzero(abs(axis-y)<=6*rh)
    if not len(ix) or not len(iy):raise ValueError('No local valid-area grid')
    axes[1,2].imshow(area[np.ix_(iy,ix)],origin='lower',cmap='cividis',vmin=0,vmax=1,
        extent=[axis[ix[0]]-step/2-x,axis[ix[-1]]+step/2-x,
                axis[iy[0]]-step/2-y,axis[iy[-1]]+step/2-y])
    axes[1,2].set(title='Usable optical exposure',xlabel='East (arcmin)',ylabel='North (arcmin)')
    fig.suptitle(label+' | measured photometry and unweighted source positions\n'
                 'Errors in colour and g share g; displayed bars are marginal. Model is a hypothesis.')
    fig.savefig(output,dpi=150);plt.close(fig)
    return dict(selected_core=int(core.sum()),selected_background=int(off.sum()),
                image_halfwidth_arcsec=halfwidth,images_cover_two_rh_square=halfwidth>=2*rh*60,
                images=image_status,probabilities_or_scores_rendered=False,
                source_overlay_or_contributor_order_rendered=False)


def pilot(case_id):
    from scripts.v14_review_evidence import packet
    base=Path('results/v14/shortlist')
    cases=[c for c in read_csv(base/'cases.csv') if c['case_id']==case_id]
    if len(cases)!=1:raise ValueError('Pilot must name one existing frozen case')
    case=cases[0];folder,_=packet(case)
    if folder is None:raise ValueError('No completed saved modes')
    # Identity/rank crosswalk and evidence stay private; no final population draw.
    out=Path('results/v14/human_review/final_private/renderer_pilot')/case_id
    if out.exists():raise ValueError('Preserve previous pilot bytes; do not overwrite')
    out.mkdir(parents=True)
    integrity=Path('results/v14/human_review/membership_integrity.json')
    proof=json.loads(integrity.read_text())
    if sha(integrity.with_suffix('.csv'))!=proof['csv_sha256']:raise ValueError('Integrity clock differs')
    snapshots={(r['case_id'],int(r['seed_rank'])):r for r in read_csv(integrity.with_suffix('.csv'))}
    modes=[r for r in read_csv(folder/'review_modes.csv') if r['fit_status']=='complete']
    modes.sort(key=lambda r:(float(r['fit_dm']),float(r['fit_rh_arcmin']),float(r['fit_ra_deg']),float(r['fit_dec_deg'])))
    config=Path('configs/v14/cohorts')/case['cohort'];os.environ['LS_SAT_CONFIG_DIR']=str(config)
    _,_,cfg=settings();region=cfg.get('region','south')
    root=Path(os.environ['LS_DR11_ROOT']);data=Path(os.environ['LS_SAT_DATA'])
    bricks=load_bricks(root,region)
    manifest=Path(f'regional_v14_{case["cohort"]}/results/summary/{case["field"]}-base/manifest.json')
    field,sources,area,_=field_cache(root,data,json.loads(manifest.read_text())['field'],cfg,bricks)
    sample,_,_,_,chosen=select(sources,field,area,cfg)
    source_ids={tuple(k) for k in sources[['RELEASE','BRICKID','OBJID']][chosen]}
    model=load_isochrone(data/'resources'/cfg['isochrone'])[0]
    records=[]
    for i,mode in enumerate(modes):
        snapshot=snapshots[(case_id,int(float(mode['rank'])))];membership=data/snapshot['frozen_path']
        if sha(membership)!=snapshot['membership_sha256']:raise ValueError('Frozen membership changed')
        with np.load(membership,allow_pickle=False) as saved:
            if not {tuple(k) for k in saved['source_ids']}<=source_ids:raise ValueError('Mode/selection differs')
        label=f'A001 / alternative {i+1:02d}';path=out/f'alternative_{i+1:02d}.png'
        status=render(path,label,sample,area,field,model,mode,root,region,bricks)
        records.append(dict(rank=mode['rank'],membership_sha256=snapshot['membership_sha256'],
                            output=path.name,sha256=sha(path),**status))
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),case_id=case_id,
        mode_table_sha256=sha(folder/'review_modes.csv'),source_manifest_sha256=sha(manifest),
        renderer_sha256=sha(Path(__file__)),image_renderer_sha256=sha(Path('src/ls_satsearch/review.py')),
        selection_sha256=sha(config/'search.yaml'),modes=records,
        final_review_release=False,previously_exposed_case=True,
        scope='Private real-data renderer pilot only. All complete modes of one old case, neutral ordering, no probabilities/scores/environment labels. Not final sample selection, contributor/radial/context evidence or PDF/ZIP QA. Frozen75 untouched.'))
    print(dict(modes=len(records),private_renderer_pilot=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True)
    pilot(p.parse_args().case)
