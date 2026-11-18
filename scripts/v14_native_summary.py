"""Summarize all seven completed native CCD experiments with their own denominators."""
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from v12_footprint import save
from v12_selection_stats import interval


def run():
    root=Path('results/v14/image_response')
    sites=read_csv(Path('configs/v14/image_fields.csv'))
    stage_rows=[];outcomes=[];inputs=[]
    for site in sites:
        p=root/f"{site['field']}-stages.csv"
        q=root/f"{site['field']}-blind.csv"
        stage_rows.extend(dict(r,cohort=site['cohort']) for r in read_csv(p))
        outcomes.extend(dict(r,cohort=site['cohort']) for r in read_csv(q))
        inputs.extend((p,q))
    bucket=defaultdict(list)
    for r in stage_rows:
        key=tuple(r[k] for k in ('site','cohort','arm','g_lo','g_hi','environment'))
        bucket[key].append(r)
    rows=[]
    for key,group in sorted(bucket.items()):
        if len(group)!=8 or len({r['trial'] for r in group})!=8:
            raise ValueError(f'CCD stage grid is incomplete at {key}')
        values=[sum(int(r[k]) for r in group) for k in ('exposed','detected','psf','selected')]
        if values!=sorted(values,reverse=True):
            raise ValueError(f'Invalid probability denominators {values}')
        row=dict(zip(('site','cohort','arm','g_lo','g_hi','environment'),key))
        row.update(dict(zip(('exposed','detected','psf','selected'),values)))
        for name,a,b in zip(('detected','psf_given_detected','selected_given_psf'),values[1:],values):
            low,high=interval(a,b) if b else (None,None)
            row.update({name+'_fraction':a/b if b else None,name+'_lo':low,name+'_hi':high})
        rows.append(row)
    write_csv(root/'all_sites_stage_probabilities.csv',rows)
    recovery=[]
    for cohort in sorted({s['cohort'] for s in sites}):
        for arm in sorted({r['arm'] for r in outcomes if r['cohort']==cohort}):
            rr=[r for r in outcomes if r['cohort']==cohort and r['arm']==arm]
            report=dict(cohort=cohort,arm=arm,trials=len(rr),sites=len({r['site'] for r in rr}),
                        selected_stars=sum(int(r['N_used']) for r in rr),
                        blank_spatial=sum(r['blank_spatial']=='True' for r in rr))
            for key in ('spatial','correct_mode_exists','blind_correct','passes_C_stability_proxy'):
                k=sum(r[key]=='True' for r in rr)
                low,high=interval(k,len(rr))
                report.update({key:k,key+'_fraction':k/len(rr),key+'_low':low,key+'_high':high})
            recovery.append(report)
    write_csv(root/'seven_background_recovery.csv',recovery)
    write_csv(root/'blind_recovery.csv',outcomes)
    paired=[]
    for cohort in ('south_ps1','north'):
        bucket=defaultdict(dict)
        for row in outcomes:
            if row['cohort']!=cohort:
                continue
            key=(row['site'],row['trial'])
            if row['arm'] in bucket[key]:
                raise ValueError(f'Duplicate native trial arm {key}')
            bucket[key][row['arm']]=row
        for key,arms in bucket.items():
            if set(arms)!=set(('ls_base','ls_deep')):
                raise ValueError(f'Unpaired native trial {key}')
            for column in ('D_kpc','rh_pc','N_imf','model_sha256','seed','truth_ra_deg','truth_dec_deg'):
                if arms['ls_base'][column]!=arms['ls_deep'][column]:
                    raise ValueError(f'Physical realization differs between arms: {key}/{column}')
        distances=['all']+sorted({p['ls_base']['D_kpc'] for p in bucket.values()},key=float)
        for distance in distances:
            pairs=[v for v in bucket.values() if distance=='all' or v['ls_base']['D_kpc']==distance]
            n=len(pairs)
            for metric in ('spatial','correct_mode_exists','blind_correct','passes_C_stability_proxy'):
                base=np.array([p['ls_base'][metric]=='True' for p in pairs])
                deep=np.array([p['ls_deep'][metric]=='True' for p in pairs])
                wins=int((deep&~base).sum());losses=int((base&~deep).sum())
                lo_w,hi_w=interval(wins,n,.975);lo_l,hi_l=interval(losses,n,.975)
                paired.append(dict(cohort=cohort,D_kpc=distance,metric=metric,trials=n,
                    sites=len({p['ls_base']['site'] for p in pairs}),deeper_only=wins,baseline_only=losses,
                    both=int((deep&base).sum()),neither=int((~deep&~base).sum()),
                    deeper_minus_baseline=(wins-losses)/n,conservative_lower=lo_w-hi_l,
                    conservative_upper=hi_w-lo_l))
    write_csv(root/'paired_native_depth.csv',paired)
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),sharey=True,layout='constrained')
    for site in sites:
        for ax,metric in zip(axes,('detected','psf_given_detected','selected_given_psf')):
            arm='ls_deep' if site['cohort'] in ('north','south_ps1') else 'ls_base'
            subset=[r for r in rows if r['site']==site['field'] and r['arm']==arm and r['environment']=='all' and
                    float(r['g_lo'])>=20 and r[metric+'_fraction'] is not None]
            x=np.array([(float(r['g_lo'])+float(r['g_hi']))/2 for r in subset])
            ax.plot(x,[r[metric+'_fraction'] for r in subset],'.-',ms=4,lw=.9,label=site['field'].removeprefix('v14_'))
            ax.set(xlabel='Injected g₀',ylim=(-.04,1.04))
            ax.grid(alpha=.15)
    for ax,title in zip(axes,('New source detection','PSF among detected sources','gr cuts among PSF sources')):
        ax.set_title(title)
    axes[0].set_ylabel('Conditional probability')
    axes[0].legend(fontsize=6,frameon=False)
    with plt.rc_context({'font.family':'serif','pdf.fonttype':42,'svg.fonttype':'none'}):
        save(fig,root/'seven_background_probability_chain')
    write_json(root/'seven_background_manifest.json',dict(inputs={str(p):sha(p) for p in inputs},
                physical_realizations=56,arm_records=len(outcomes),
                scope='Eight physical realizations per real CCD background. Conditional stage probabilities and sampled-background recovery. Paired depth intervals are conservative trial-level bounds and do not model field variation. C stability is a diagnostic proxy; independent confirmation and population completeness require further evidence.'))


if __name__=='__main__':
    run()
