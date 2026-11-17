"""Render review load, Table 8 recovery, and loaded coadd-response measurements."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
import yaml

from ls_satsearch.run import read_csv, write_csv
from v12_selection_stats import interval


LAYER={'north':'North BASS','south_ps1':'South PS1',
       'south_delve':'South DELVE','south_des':'South DES'}
COLOR=('#345b93','#3c8257','#be7f42','#8b507e')


def save(fig,out,name):
    for ext in ('png','pdf','svg'):
        dest=out/f'{name}.{ext}'
        fig.savefig(dest,dpi=195)
        if ext=='svg':
            dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
    plt.close(fig)


def discovery(root, output):
    counts, scores = {l:[] for l in LAYER.values()},{l:[] for l in LAYER.values()}
    for p in sorted((root/'discovery').glob('*/*/main/sky_group_comparison.csv')):
        layer=LAYER[p.parent.parent.name]
        counts[layer].extend(read_csv(p))
        scores[layer].extend(float(r['score']) for r in read_csv(p.parent/'sky_group_candidates.csv')
                             if r['representative']=='True' and r['budget']=='0.3')
    summaries=[]
    for layer in LAYER.values():
        for budget in (.1,.3):
            rows=[r for r in counts[layer] if float(r['budget'])==budget]
            if rows:
                area=sum(float(r['eval_area_deg2']) for r in rows)
                n=sum(int(r['evaluation_sky_groups']) for r in rows)
                summaries.append(dict(layer=layer,budget=budget,area_deg2=area,n_groups=n,
                                      groups_per_deg2=n/area,cutoffs=';'.join(sorted({r['cutoff'] for r in rows}))))
    if not summaries:
        return
    write_csv(output/'discovery_summary.csv',summaries)
    fig,ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for i,layer in enumerate(LAYER.values()):
        c=COLOR[i]
        values=np.sort(scores[layer])
        if len(values):
            ax[0].step(values,np.arange(len(values),0,-1)/len(values),where='post',c=c,label=layer)
        for j,budget in enumerate((.1,.3)):
            r=next((r for r in summaries if r['layer']==layer and r['budget']==budget),None)
            if r:
                ax[1].scatter(i+(.15 if j else -.15),r['groups_per_deg2'],c=c,marker='o' if j else 'x')
    ax[0].legend(frameon=False,fontsize=8)
    ax[0].set(xlabel='A score at group anchor',ylabel='Fraction of retained groups ≥ score')
    ax[1].axhline(.3,c='.6',lw=.7,ls=':')
    ax[1].set_xticks(range(len(LAYER)),LAYER.values(),rotation=20,ha='right')
    ax[1].set_ylabel('Observed review groups per effective deg²')
    ax[1].scatter([],[],color='.4',marker='x',label='Strict budget')
    ax[1].scatter([],[],color='.4',marker='o',label='Primary budget')
    ax[1].legend(frameon=False,fontsize=8)
    save(fig,output,'discovery_review_load')


def observing_summary(root,output):
    by_layer={name:[] for name in LAYER.values()}
    for path in sorted((root/'discovery').glob('*/*/field_metrics.csv')):
        by_layer[LAYER[path.parent.name]].extend(read_csv(path))
    rows=[]
    for name,fields in by_layer.items():
        if not fields:
            continue
        def values(key):
            return np.array([float(r[key]) for r in fields if r.get(key)])
        source_psf=np.array([int(r['inner_psf']) for r in fields])
        source_other=np.array([int(r['inner_non_psf']) for r in fields])
        psf_fraction=source_psf/np.maximum(1,source_psf+source_other)
        rows.append(dict(layer=name,fields=len(fields),median_corrected_g5=np.median(values('g_depth')),
                         median_corrected_r5=np.median(values('r_depth')),
                         median_g_seeing_arcsec=np.median(values('g_seeing')),
                         median_psf_fraction=np.median(psf_fraction),
                         scope='Medians of field medians over selected sources'))
    if rows:
        write_csv(output/'observing_conditions.csv',rows)


def controls(root,output):
    rows=read_csv(root/'table8/tan_table8_ls.csv')
    targets=list(dict.fromkeys(r['name'] for r in rows))
    fig,ax=plt.subplots(1,2,figsize=(10,4.3),layout='constrained')
    for dep,c,mark in (('base',COLOR[0],'o'),('deep',COLOR[2],'^')):
        chosen=[r for r in rows if r['depth']==dep and r.get('blind_dm')]
        x=np.array([targets.index(r['name']) for r in chosen]) + (.12 if dep=='deep' else -.12)
        ax[0].scatter(x,[float(r['blind_delta_dm']) for r in chosen],c=c,marker=mark,label='LS '+dep)
        ax[1].scatter(x,[float(r['blind_offset_per_rh']) for r in chosen],c=c,marker=mark)
    ax[0].axhspan(-.25,.25,color='.8',alpha=.4)
    ax[1].axhline(1,c='.5',ls='--',lw=.7)
    ax[0].set_ylabel('Blind peak minus literature DM (mag)')
    ax[1].set_ylabel(r'Angular offset / literature $r_h$')
    ax[0].legend(frameon=False,fontsize=8)
    for a in ax:
        a.set_xticks(range(len(targets)),targets,rotation=30,ha='right')
    save(fig,output,'table8_blind_recovery')


def image(root,output):
    fig,ax=plt.subplots(1,2,figsize=(10,4),sharey=True,layout='constrained')
    table=[]
    for p in sorted((root/'image_response').glob('*.csv')):
        rows=read_csv(p)
        region=rows[0]['region']
        mags=sorted({float(r['mag0']) for r in rows})
        color=COLOR[0 if region=='north' else 1]
        for subplot,band in zip(ax,'gr'):
            for site in ('uniform','near_peak'):
                pp=[]
                for m in mags:
                    sub=[r for r in rows if (r['site'],r['band'],float(r['mag0']))==(site,band,m)]
                    n=sum(int(r['n']) for r in sub)
                    k=sum(int(r['new_peak']) for r in sub)
                    if n:
                        low,high=interval(k,n)
                        row=dict(region=region,band=band,site=site,mag0=m,n=n,k=k,p=k/n,lo=low,hi=high)
                        pp.append(row)
                        table.append(row)
                subplot.plot([r['mag0'] for r in pp],[r['p'] for r in pp],
                             marker='o',ms=3,lw=1,linestyle='-' if site=='uniform' else ':',
                             color=color,label=f"{region.title()} · {site.replace('_',' ')}")
                subplot.set_xlabel('Injected '+band+'₀ (mag)')
    ax[0].set_ylabel('Fraction with a new coadd detection')
    ax[1].legend(frameon=False,fontsize=8)
    save(fig,output,'coadd_detection_response')
    write_csv(output/'coadd_detection_response.csv',table)


def visual_context(root):
    checks=yaml.safe_load(Path('configs/v12/visual_context.yaml').read_text())
    results=[]
    seen=set()
    for check in checks:
        center=SkyCoord(check['ra'],check['dec'],unit='deg')
        table=root/'discovery/v12'/check['layer']/'main/sky_group_candidates.csv'
        if not table.exists():
            continue
        for row in read_csv(table):
            if (row['representative']!='True' or row['budget']!='0.3' or row['field']!=check['field']
                    or row['group_id'] in seen or
                    float(row['rh_arcmin'])<check.get('min_rh_arcmin',0) or
                    row['group_id']!=check.get('group',row['group_id'])):
                continue
            pos=SkyCoord(float(row['ra_deg']),float(row['dec_deg']),unit='deg')
            separation=center.separation(pos).arcmin
            if separation<=check['radius_arcmin']:
                seen.add(row['group_id'])
                results.append(dict(group_id=row['group_id'],known_context=check['name'],
                    center_separation_arcmin=separation,contextual_radius_arcmin=check['radius_arcmin'],
                    **{k:check[k] for k in ('triage','reason','source')}))
    if results:
        write_csv(root/'discovery/visual_context.csv',results)


if __name__=='__main__':
    root=Path('results/v12')
    out=root/'figures'
    out.mkdir(exist_ok=True,parents=True)
    visual_context(root)
    with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
        discovery(root,out)
        observing_summary(root,out)
        controls(root,out)
        image(root,out)
