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


def figure(output, recovery, paired):
    # A gridded display only; avoid interpolating the sparse cells into a
    # claimed continuous selection function.
    version='v12' if any(r['version']=='v12' for r in recovery) else 'v10'
    regions=sorted({r['region'] for r in recovery if r['version']==version})
    fig,axs=plt.subplots(2,len(regions),figsize=(6.1*len(regions),7.7),squeeze=False,layout='constrained')
    for j,region in enumerate(regions):
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
        all_rows.extend(dict(r,version='v12') for r in read_csv(f))
    with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
        figure(a.output,*summarize(all_rows,a.output))
