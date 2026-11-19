"""Render identity-free review evidence from actual saved C membership on Slurm."""
import argparse
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.data import load_bricks, select
from ls_satsearch.review import image_cutouts
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_json
from ls_satsearch.search import load_isochrone


def packet(case):
    base=Path('results/v14/shortlist')
    for name in ('cases','cached_cases'):
        folder=base/name/case['case_id']
        path=folder/'review_modes.csv'
        if path.is_file():
            rows=[r for r in read_csv(path) if r['fit_status']=='complete']
            if rows:return folder,max(rows,key=lambda r:float(r['ts']))
    return None,None


def run(case_id=None, require_all=False):
    base=Path('results/v14/shortlist')
    cases=read_csv(base/'cases.csv')
    if case_id:cases=[r for r in cases if r['case_id']==case_id]
    if case_id and not cases:raise ValueError('Unknown case ID')
    if require_all and any(packet(c)[1] is None for c in cases):
        raise ValueError('Full review evidence requires every registered C packet; pending cases are not silently omitted')
    root=Path(os.environ['LS_DR11_ROOT']);data_root=Path(os.environ['LS_SAT_DATA'])
    bricks_by_region={}
    for case in cases:
        folder,mode=packet(case)
        if mode is None:continue
        rank=int(float(mode['rank']));cohort=case['cohort'];field_id=case['field']
        output=base/'evidence'/case['case_id'];output.mkdir(parents=True,exist_ok=True)
        membership=data_root/'runs/v14'/f'{field_id}-base'/f'membership-main-A-{rank}.npz'
        config=Path('configs/v14/cohorts')/cohort
        previous=output/'provenance.json'
        if previous.is_file():
            old=json.loads(previous.read_text())
            if (old['mode_table_sha256']==sha(folder/'review_modes.csv') and
                old['membership_sha256']==sha(membership) and
                old.get('renderer_sha256')==sha(Path(__file__)) and
                old.get('image_renderer_sha256')==sha(Path('src/ls_satsearch/review.py')) and
                all((output/name).is_file() for name in ('evidence.png','images.png'))):
                print(case['case_id'],'existing evidence verified',flush=True);continue
        os.environ['LS_SAT_CONFIG_DIR']=str(config)
        _,_,cfg=settings();region=cfg.get('region','south')
        if region not in bricks_by_region:bricks_by_region[region]=load_bricks(root,region)
        bricks=bricks_by_region[region]
        manifest=Path(f'regional_v14_{cohort}/results/summary/{field_id}-base/manifest.json')
        spec=json.loads(manifest.read_text())['field']
        field,sources,area,_=field_cache(root,data_root,spec,cfg,bricks)
        sample,_,valid,mags,chosen=select(sources,field,area,cfg)
        with np.load(membership,allow_pickle=False) as saved:
            probabilities={tuple(k):float(p) for k,p in zip(saved['source_ids'],saved['probability'])}
        ids=sources[['RELEASE','BRICKID','OBJID']][chosen]
        lookup={tuple(k):i for i,k in enumerate(ids)}
        if not probabilities.keys()<=lookup.keys():
            raise ValueError(f'Saved membership does not match selected catalogue: {case["case_id"]}')
        prob=np.zeros(len(sample))
        for key,value in probabilities.items():prob[lookup[key]]=value
        x,y=field.xy(float(mode['fit_ra_deg']),float(mode['fit_dec_deg']))
        rh=float(mode['fit_rh_arcmin']);dm=float(mode['fit_dm'])
        radius=np.linalg.norm(sample[:,:2]-(x,y),axis=1)
        core=radius<=1.5*rh
        off=(radius>3.5*rh)&(radius<np.sqrt(3.5**2+1.5**2)*rh)
        model=load_isochrone(data_root/'resources'/cfg['isochrone'])[0]
        fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
        near=radius<=6*rh
        axes[0,0].scatter(*(sample[near,:2]-(x,y)).T,s=7,c='#b6b6b6')
        members=prob>.05
        axes[0,0].scatter(*(sample[members,:2]-(x,y)).T,s=17,c=prob[members],cmap='plasma',vmin=0,vmax=1)
        axes[0,0].add_patch(plt.Circle((0,0),rh,fill=False,color='tab:blue'))
        axes[0,0].set(xlabel='East (arcmin)',ylabel='North (arcmin)',title='Selected sources and C membership',
                      xlim=(-6*rh,6*rh),ylim=(-6*rh,6*rh),aspect='equal')
        for ax,use,title in ((axes[0,1],core,'Core'),(axes[1,0],off,'Equal geometric area background')):
            stars=sample[use];g,r=stars[:,2:4].T;eg,er=stars[:,4:6].T
            ax.errorbar(g-r,g,xerr=np.hypot(eg,er),yerr=eg,fmt='.',ms=3,lw=.45,alpha=.55,color='#5f89a5')
            selected=use&members
            ax.scatter(sample[selected,2]-sample[selected,3],sample[selected,2],s=12,
                       facecolors='none',edgecolors='#bb5f31')
            ax.plot(model[:,0]-model[:,1],model[:,0]+dm,'.',color='#be3c36',ms=1.5)
            ax.set(xlim=(-.5,1.8),ylim=(max(23.5,g.max(initial=23.5)),15),
                   xlabel='(g-r)0 (mag)',ylabel='g0 (mag)',title=f'{title}: {int(use.sum())} sources')
        names=sources.dtype.names
        sx,sy=field.xy(sources['RA'],sources['DEC'])
        allcore=np.hypot(sx-x,sy-y)<=1.5*rh
        flags={}
        for column,bit,label in [('FITBITS',0,'forced_PSF'),('FITBITS',12,'Gaia_pointsource'),
                                 ('MASKBITS',13,'CLUSTER'),('MASKBITS',17,'RESOLVED'),('MASKBITS',19,'WISE_GAIA')]:
            flags[label]=int((allcore&chosen&((sources[column]&(1<<bit))!=0)).sum()) if column in names else None
        ax=axes[1,1];ax.axis('off')
        ax.text(.03,.95,'Core sample / quality context',va='top',fontsize=12)
        text=[f'Selected PSF: {int((allcore&chosen).sum())}',
              f'Other valid catalogue sources: {int((allcore&valid&~chosen).sum())}']
        text += [f'{k}: {v if v is not None else "unavailable"}' for k,v in flags.items()]
        text += ['','Colour errors share g with the vertical axis.',
                 'Displayed errors are marginal, not independent.',
                 'Background area is geometric; inspect masks separately.',
                 'C membership and source flags are not stellar truth.']
        ax.text(.03,.83,'\n'.join(text),va='top',fontsize=10,linespacing=1.5)
        if case['queue']!='priority':
            # Known-system processing flags are part of the sealed identity key.
            ax.clear();ax.axis('on')
            step=2*field.limit/len(area)
            axis=(np.arange(len(area))+.5)*step-field.limit
            ix=np.flatnonzero(abs(axis-x)<=6*rh);iy=np.flatnonzero(abs(axis-y)<=6*rh)
            ax.imshow(area[np.ix_(iy,ix)],origin='lower',cmap='cividis',vmin=0,vmax=1,
                      extent=[axis[ix[0]]-x,axis[ix[-1]]-x,axis[iy[0]]-y,axis[iy[-1]]-y])
            ax.set(xlabel='East (arcmin)',ylabel='North (arcmin)',title='Usable optical exposure mask')
        fig.suptitle(case['case_id']+' | observed morphology, CMD and spatial evidence')
        fig.savefig(output/'evidence.png',dpi=150);plt.close(fig)
        indices=np.flatnonzero(prob>0)
        status=image_cutouts(output/'images.png',root,bricks,field,
            dict(x=x,y=y,rh_arcmin=rh),sample[indices,:2],prob[indices],details=True,
            region=region,anonymous_label=case['case_id'])
        write_json(output/'provenance.json',dict(case_id=case['case_id'],job=os.getenv('SLURM_JOB_ID'),
            saved_mode_rank=rank,mode_table_sha256=sha(folder/'review_modes.csv'),
            renderer_sha256=sha(Path(__file__)),
            image_renderer_sha256=sha(Path('src/ls_satsearch/review.py')),
            source_manifest_sha256=sha(manifest),
            membership_sha256=sha(membership),selection_sha256=sha(config/'search.yaml'),
            selected_core=int(core.sum()),background_sources=int(off.sum()),flags=flags,**status,
            scope='Actual saved C membership and selected measured photometry. No new fit, review grade or identity in the rendered panels. Marginal errors only; g-colour covariance is acknowledged. Revealing environment/score belongs to the separate key.'))
        print(case['case_id'],'evidence complete',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case')
    parser.add_argument('--require-all',action='store_true');args=parser.parse_args()
    run(args.case,args.require_all)
