"""Summarize physical recovery by region, with sparse-bin and paired intervals."""

import argparse
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binomtest

from ls_satsearch.run import read_csv, write_csv


SURVEYS=('ls_base','ls_deep','ps1')
LABELS=('LS baseline','LS deeper','PS1 DR2')
COLORS=('#47688c','#bd622b','#4b845e')


def interval(k,n,level=.95):
    bounds=binomtest(k,n).proportion_ci(confidence_level=level,method='exact')
    return bounds.low,bounds.high


def summarize(trials, output):
    # Keep historical search versions and freeze points identifiable. Subsets
    # inherit the measured catalog-level search response of their own run.
    cohorts=defaultdict(dict)
    for r in trials:
        key=(r['version'],r.get('region') or 'south',float(r['D_kpc']),float(r['rh_pc']),
             float(r['expected_MV_proxy']))
        trial_id=(r['field'],r['trial'])
        record=cohorts[key].setdefault(trial_id,{})
        if r['survey'] in record:
            raise ValueError(f'Duplicate {key}/{trial_id}/{r["survey"]}')
        record[r['survey']]=r
    recovery, paired = [], []
    for (version,region,distance,rh,mv),bucket in sorted(cohorts.items()):
        n=len(bucket)
        if any(set(p)!=set(SURVEYS) for p in bucket.values()):
            raise ValueError(f'Unpaired search arms in {version}/{region}/{distance}/{rh}/{mv}')
        parameters=dict(version=version,region=region,D_kpc=distance,rh_pc=rh,
                        expected_MV_proxy=mv,N=n,backgrounds=len({a[0] for a in bucket}))
        for metric in ('spatial','correct_mode_exists','blind_correct'):
            results={s:np.array([p[s][metric]=='True' for p in bucket.values()]) for s in SURVEYS}
            for survey in SURVEYS:
                k=int(results[survey].sum())
                lo,hi=interval(k,n)
                recovery.append(dict(parameters,metric=metric,survey=survey,N_recovered=k,
                                     p=k/n,p_low=lo,p_high=hi))
            for a,b in (('ls_base','ps1'),('ls_deep','ps1'),('ls_deep','ls_base')):
                wins=int((results[a]&~results[b]).sum())
                losses=int((~results[a]&results[b]).sum())
                lo_a,hi_a=interval(wins,n,.975)
                lo_b,hi_b=interval(losses,n,.975)
                paired.append(dict(parameters,metric=metric,first=a,second=b,wins=wins,losses=losses,
                                   both=int((results[a]&results[b]).sum()),
                                   neither=n-wins-losses-int((results[a]&results[b]).sum()),
                                   difference=(wins-losses)/n,lower=lo_a-hi_b,upper=hi_a-lo_b))
    output.mkdir(exist_ok=True,parents=True)
    write_csv(output/'conditional_efficiency.csv',recovery)
    write_csv(output/'paired_difference.csv',paired)
    return recovery,paired


def display_versions(rows):
    # Keep a re-used background with its own search and cutoff version.
    latest={}
    for region in sorted({r['region'] for r in rows}):
        versions={r['version'] for r in rows if r['region']==region}
        latest[region]=next(v for v in ('v12','v12-south-archive','v10','v9') if v in versions)
    return latest


def figure(output, recovery, paired):
    # A gridded display only; avoid interpolating the sparse cells into a
    # claimed continuous selection function.
    versions=display_versions(recovery)
    regions=list(versions)
    fig,axs=plt.subplots(2,len(regions),figsize=(6.1*len(regions),7.7),squeeze=False,layout='constrained')
    for j,region in enumerate(regions):
        version=versions[region]
        rows=[r for r in recovery if r['version']==version and r['region']==region and r['metric']=='spatial']
        cells=sorted({(r['D_kpc'],r['rh_pc'],r['expected_MV_proxy']) for r in rows})
        index={cell:i for i,cell in enumerate(cells)}
        ax=axs[0,j]
        for i,(s,label,color) in enumerate(zip(SURVEYS,LABELS,COLORS)):
            rr=[r for r in rows if r['survey']==s]
            x=[index[(r['D_kpc'],r['rh_pc'],r['expected_MV_proxy'])]+.19*(i-1) for r in rr]
            y=np.array([r['p'] for r in rr])
            ax.errorbar(x,y,yerr=np.maximum(0,[y-np.array([r['p_low'] for r in rr]),
                                               np.array([r['p_high'] for r in rr])-y]),
                        fmt='o',ms=3,lw=.8,c=color,capsize=2,label=label)
        ax.set_ylabel('Spatial recovery probability')
        ax.set_ylim(-.05,1.05)
        ax.set_title(f'{region.title()} · {version}')
        ax.legend(fontsize=8,frameon=False)
        ax.set_xticks(range(len(cells)),[])
        ax.grid(axis='y',alpha=.22)
        ax=axs[1,j]
        rr=[r for r in paired if r['version']==version and r['region']==region and
            r['metric']=='spatial' and r['second']=='ps1']
        for i,(s,color) in enumerate(zip(SURVEYS[:2],COLORS[:2])):
            sub=[r for r in rr if r['first']==s]
            x=[index[(r['D_kpc'],r['rh_pc'],r['expected_MV_proxy'])]+.18*(i-.5) for r in sub]
            y=np.array([r['difference'] for r in sub])
            ax.errorbar(x,y,yerr=np.maximum(0,[y-np.array([r['lower'] for r in sub]),
                                               np.array([r['upper'] for r in sub])-y]),
                        fmt='o',c=color,ms=3,capsize=2,lw=.8)
        ax.axhline(0,ls='--',lw=.8,c='0.5')
        ax.set_ylim(-1.05,1.05)
        ax.set_ylabel(r'$P_{\rm LS}-P_{\rm PS1~DR2}$')
        ax.set_xticks(range(len(cells)),[f'{a:g}/{b:g}/{c:g}' for a,b,c in cells],rotation=72,fontsize=7)
        ax.set_xlabel(r'$D$ (kpc) / $r_h$ (pc) / expected $M_{V,\rm proxy}$ (mag)')
    for ext in ('png','pdf','svg'):
        dest=output/f'conditional_efficiency.{ext}'
        fig.savefig(dest,dpi=200)
        if ext=='svg':
            dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
    plt.close(fig)


def paired_heatmap(output, paired):
    versions=display_versions(paired)
    shown=[r for r in paired if r['version']==versions[r['region']] and r['metric']=='spatial'
           and r['second']=='ps1' and r['first']=='ls_deep']
    if not shown:
        return
    regions=sorted({r['region'] for r in shown})
    distances=sorted({r['D_kpc'] for r in shown})
    radii=sorted({r['rh_pc'] for r in shown})
    light=sorted({r['expected_MV_proxy'] for r in shown})
    fig,axs=plt.subplots(len(regions),len(distances),figsize=(3.4*len(distances),3.2*len(regions)),
                         squeeze=False,layout='constrained')
    for row,region in enumerate(regions):
        for col,dist in enumerate(distances):
            axis=axs[row,col]
            data=np.full((len(radii),len(light)),np.nan)
            d={(r['rh_pc'],r['expected_MV_proxy']):r for r in shown
               if (r['region'],r['D_kpc'])==(region,dist)}
            for y,rh in enumerate(radii):
                for x,mv in enumerate(light):
                    point=d.get((rh,mv))
                    if point is None:
                        continue
                    data[y,x]=point['difference']
                    string=f"{point['wins']-point['losses']:+d}/{point['N']}"
                    axis.text(x,y,string,ha='center',va='center',fontsize=9,
                              color='white' if abs(point['difference'])>.6 else 'black')
            c=axis.imshow(data,cmap='RdBu_r',vmin=-1,vmax=1,origin='lower',aspect='auto')
            axis.set_facecolor('#e7e7e7')
            axis.set_title(f'{region.title()} · {dist:g} kpc')
            axis.set_xticks(range(len(light)),[f'{v:g}' for v in light])
            axis.set_yticks(range(len(radii)),[f'{v:g}' for v in radii])
            if col==0:
                axis.set_ylabel('Half-light radius (pc)')
            if row==len(regions)-1:
                axis.set_xlabel('Expected integrated V proxy (mag)')
    fig.colorbar(c,ax=axs,label='Paired efficiency difference (deeper LS − PS1 DR2)',shrink=.8)
    for ext in ('png','pdf','svg'):
        dest=output/f'paired_difference_heatmap.{ext}'
        fig.savefig(dest,dpi=200)
        if ext=='svg':
            dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
    plt.close(fig)


def background_summary(files, output):
    rows=[]
    for file in files:
        trials=read_csv(file)
        if not trials:
            continue
        errors=read_csv(file.with_name(file.stem+'-ls-error-by-type.csv'))
        g_sigma=next((r['sigma_p50'] for r in errors if r['band']=='g'
                      and r['morphology']=='point' and r['bin_center']=='23.0'),None)
        for s in SURVEYS:
            arm=[r for r in trials if r['survey']==s]
            if not arm:
                continue
            n=len(arm)
            recovered=sum(r['spatial']=='True' for r in arm)
            lo,hi=interval(recovered,n)
            rows.append(dict(field=arm[0]['field'],region=arm[0].get('region'),
                             survey=s,ls_g23_point_error=g_sigma,N=n,recovered=recovered,
                             fraction=recovered/n,lower=lo,upper=hi,
                             correct_distance=sum(r['correct_mode_exists']=='True' for r in arm),
                             blank_spatial=sum(r['blank_spatial']=='True' for r in arm),
                             latent=sum(int(r['N_latent']) for r in arm),
                             selected=sum(int(r['N_used']) for r in arm),
                             unsupported=sum(int(r['N_response_unsupported']) for r in arm)))
    if not rows:
        return
    write_csv(output/'background_efficiency.csv',rows)
    fig,ax=plt.subplots(figsize=(6.5,4.1),layout='constrained')
    for survey,label,color in zip(SURVEYS,LABELS,COLORS):
        selected=[r for r in rows if r['survey']==survey and r['ls_g23_point_error']]
        if selected:
            p=np.array([r['fraction'] for r in selected])
            ax.errorbar([float(r['ls_g23_point_error']) for r in selected],p,
                        yerr=np.maximum(0,[p-np.array([r['lower'] for r in selected]),
                                           np.array([r['upper'] for r in selected])-p]),
                        label=label,c=color,fmt='o',ms=4,capsize=2,lw=.7)
    ax.set_ylabel('Recovery across the sampled physical grid')
    ax.set_xlabel('Local LS g=23 point-source median error (mag)')
    ax.set_ylim(-.03,1.03)
    ax.legend(frameon=False,fontsize=8)
    for ext in ('png','pdf','svg'):
        dest=output/f'background_efficiency.{ext}'
        fig.savefig(dest,dpi=200)
        if ext=='svg':
            dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--fresh',type=Path,nargs='*',default=[])
    a=p.parse_args()
    all_rows=[]
    for version,folder in (('v9','physical_trials'),('v10','compact_trials')):
        for f in sorted((Path('results')/version/folder).glob('fresh_??.csv')):
            all_rows.extend(dict(r,version=version) for r in read_csv(f))
    for f in a.fresh:
        version='v12-south-archive' if f.parent.name=='south_archive' else 'v12'
        all_rows.extend(dict(r,version=version) for r in read_csv(f))
    with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
        recovery,paired=summarize(all_rows,a.output)
        figure(a.output,recovery,paired)
        paired_heatmap(a.output,paired)
        background_summary(a.fresh,a.output)
