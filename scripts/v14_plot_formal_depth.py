"""Plot accepted paired formal-policy recovery, retaining its finite-grid limits."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv,sha,write_json

ROOT=Path('results/v14/repeat_full/production_deeper_replay')


def run():
    acceptance=ROOT/'acceptance.json';proof=json.loads(acceptance.read_text())
    if not proof['accepted'] or proof['validated_paired_cases']!=144:
        raise ValueError('Accept the full formal pair before plotting')
    rates_path=ROOT/'fixed_background_formal_depth_recovery.csv'
    contrast_path=ROOT/'paired_formal_depth_resampling.csv'
    inputs={str(p):sha(p) for p in (acceptance,rates_path,contrast_path,ROOT/'formal_depth_pairs.csv',ROOT/'blank_response.csv')}
    rates=read_csv(rates_path);contrast=read_csv(contrast_path)
    sites=sorted({r['site'] for r in rates});out=ROOT/'figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(2,3,figsize=(12,7),sharex=True,sharey=True)
    colours=['#176b9b','#c45b23']
    for row,mv in enumerate((-3.,-1.5)):
        for col,radius in enumerate((3.,10.,30.)):
            ax=axes[row,col]
            for offset,(arm,label) in enumerate((('baseline','LS baseline'),('deeper','LS deeper'))):
                cells=[next(r for r in rates if r['site']==site and r['arm']==arm and r['metric']=='spatial'
                    and float(r['rh_pc'])==radius and float(r['target_MV_proxy'])==mv) for site in sites]
                y=np.array([float(r['fraction']) for r in cells]);x=np.arange(3)+(offset-.5)*.12
                error=np.array([[float(r['fixed_background_MC_low']) for r in cells],
                                [float(r['fixed_background_MC_high']) for r in cells]])
                ax.errorbar(x,y,yerr=np.maximum(0,np.vstack((y-error[0],error[1]-y))),
                    fmt='o',capsize=3,color=colours[offset],label=label)
            ax.set_title(f'$r_h={radius:g}$ pc; target $M_V$ proxy $={mv:g}$')
            ax.set_xticks(range(3),['sky 1','sky 2','sky 3']);ax.set_ylim(-.06,1.06)
            ax.grid(axis='y',alpha=.2)
            if col==0:ax.set_ylabel('Spatial recovery / 8 IMF draws')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.935),ncol=2,fontsize=10)
    fig.suptitle('100 kpc: paired formal A policies, fixed development-budget cuts',fontsize=14)
    fig.text(.5,.018,'Three selected backgrounds; exact fixed-background Monte Carlo intervals. Actual IMF light varies within target bins.\n'
        'Finite rendered stamps and V-band proxy; no physical PS1 response, C/human completeness or all-sky selection function.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.07,1,.95))
    for suffix in ('png','pdf'):fig.savefig(out/f'formal_spatial_recovery.{suffix}',dpi=160)
    plt.close(fig)
    cells=[r for r in contrast if r['metric']=='spatial']
    fig,ax=plt.subplots(figsize=(10,6));ys=np.arange(len(cells))[::-1]
    for y,r in zip(ys,cells):
        point=float(r['deeper_minus_baseline'])
        ax.plot([float(r['simultaneous_fixed_background_MC_low']),float(r['simultaneous_fixed_background_MC_high'])],
                [y,y],lw=5,color='#b9c0c7',label='Conservative fixed-background bound' if y==ys[0] else None)
        ax.plot([float(r['resampling_p025']),float(r['resampling_p975'])],[y,y],lw=2,color=colours[0],
                label='Crossed-resampling sensitivity (2.5–97.5%)' if y==ys[0] else None)
        ax.plot(point,y,'o',color='black')
    labels=['Equal six-cell grid' if r['rh_pc']=='all' else f"{float(r['rh_pc']):g} pc / target proxy {float(r['target_MV_proxy']):g}" for r in cells]
    ax.set_yticks(ys,labels);ax.axvline(0,color='black',lw=.8);ax.axvline(.10,color='#c45b23',ls='--',lw=1)
    ax.set_xlabel('Spatial recovery difference: deeper − baseline');ax.grid(axis='x',alpha=.2)
    ax.set_title('Shared IMF realizations across depths and three fixed skies')
    handles,labels=ax.get_legend_handles_labels()
    fig.legend(handles,labels,fontsize=8,loc='upper center',bbox_to_anchor=(.5,.135))
    fig.text(.5,.02,
        '48 potential populations, reused across skies; equal frozen-grid weights, not population or area weights.\n'
        'Resampling these three skies is a sensitivity analysis, not a validated all-sky confidence interval.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.20,1,1))
    for suffix in ('png','pdf'):fig.savefig(out/f'formal_depth_difference.{suffix}',dpi=160)
    plt.close(fig)
    if any(sha(Path(p))!=digest for p,digest in inputs.items()):raise ValueError('Accepted plot inputs changed')
    write_json(out/'manifest.json',dict(inputs=inputs,code_sha256=sha(Path(__file__)),
        outputs={str(p):sha(p) for p in out.glob('*') if p.suffix in ('.png','.pdf')},
        all_sky_selection_function=False,physical_PS1_gain=False,visual_QA_pending=True))


if __name__=='__main__':run()
