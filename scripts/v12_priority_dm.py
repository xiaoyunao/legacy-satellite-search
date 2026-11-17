"""Measure local DM response at predeclared LS/Locus apertures."""

import argparse
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import select
from ls_satsearch.run import field_cache, settings, sha, write_csv, write_json
from ls_satsearch.search import CMD, exact_onoff, load_isochrone, point_fit


def run(plan, output):
    root,data,_=settings()
    spec=yaml.safe_load(plan.read_text())
    manifest=Path(spec['field_manifest'])
    m=json.loads(manifest.read_text())
    cfg=m['config']
    field,sources,area,_=field_cache(root,data,m['field'],cfg,None)
    x,y=field.xy(spec['ra_deg'],spec['dec_deg'])
    model=load_isochrone(data/'resources'/cfg['isochrone'])
    output.mkdir(exist_ok=True,parents=True)
    rows=[]
    for limit in (0,.5):
        cuts=dict(cfg,g_max=cfg['g_max']+limit,r_max=cfg['r_max']+limit)
        sample,*_=select(sources,field,area,cuts)
        cmd=CMD(sample,model,cuts)
        tree=cKDTree(sample[:,:2])
        for dm in np.arange(13.5,22.51,.25):
            keep,ratios=cmd.weights(dm)
            peak=dict(x=x,y=y,dm=dm,rh_arcmin=spec['rh_arcmin'])
            n1,n2,a1,a2=exact_onoff(field,x,y,spec['rh_arcmin'],tree,area,keep)
            fit,ids,p=point_fit(sample,cmd,field,area,peak,ratio=ratios)
            record=dict(delta_limit_mag=limit,dm=dm,n_cmd_on=n1,n_cmd_off=n2,
                        area_on=a1,area_off=a2,fit_status='complete' if fit else 'unavailable')
            if fit is not None:
                used=np.ones(len(sample),dtype=bool)
                used[ids[np.argsort(p)[-3:]]]=False
                subset,*_=point_fit(sample[used],cmd,field,area,peak,ratio=ratios[used])
                record.update(C_TS=fit['ts'],C_TS_without_top3=subset['ts'] if subset else None)
            rows.append(record)
    write_csv(output/'distance_response.csv',rows)
    with plt.rc_context({'font.family':'serif','pdf.fonttype':42,'svg.fonttype':'none'}):
        fig,ax=plt.subplots(figsize=(6.9,3.9),layout='constrained')
        for limit,c in ((0,'#47688c'),(.5,'#bd622b')):
            subset=[r for r in rows if r['delta_limit_mag']==limit and r['fit_status']=='complete']
            d=[r['dm'] for r in subset]
            ax.plot(d,[r['C_TS'] for r in subset],color=c,label='Baseline' if not limit else 'Deeper')
            ax.plot(d,[r['C_TS_without_top3'] for r in subset],color=c,ls=':')
        ax.axvspan(16.5,20.75,color='.88',alpha=.36,label='Production main branch')
        ax.set(xlabel='Distance modulus (mag)',ylabel='Fixed-centre C TS')
        ax.legend(frameon=False,fontsize=8)
        for kind in ('pdf','svg','png'):
            dest=output/f'distance_response.{kind}'
            fig.savefig(dest,dpi=185)
            if kind=='svg':
                dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
        plt.close(fig)
    write_json(output/'distance_response.json',dict(job=os.getenv('SLURM_JOB_ID'),
               plan_sha256=sha(plan),manifest_sha256=sha(manifest),radius_arcmin=spec['rh_arcmin'],
               scope='Fixed-centre response. Dotted curves remove the top three contributions per distance.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
