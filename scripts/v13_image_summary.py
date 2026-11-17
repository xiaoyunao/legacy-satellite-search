"""Plot and summarize the native probability chain across three images."""
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, write_csv
from v12_review_stats import save
from v12_selection_stats import interval

NAMES = ('south_sharp','south_broad','north_match')
ARMS = ('ls_base','ls_deep')
STAGES=('exposed','detected','psf','selected')
PROB=('detected','psf_given_detected','selected_given_psf')


def run(path):
    tables=[r for name in NAMES for r in read_csv(path/f'{name}-stages.csv')]
    group=defaultdict(list)
    for row in tables:
        key=tuple(row[k] for k in ('site','arm','g_lo','g_hi','environment'))
        group[key].append(row)
    summary=[]
    for key, rows in sorted(group.items()):
        if len(rows)!=6:
            raise ValueError(f'Missing trial at {key}')
        values = [sum(int(r[k]) for r in rows) for k in STAGES]
        record=dict(zip(('site','arm','g_lo','g_hi','environment'),key))
        record.update(dict(zip(STAGES,values)))
        record['initial']=sum(int(r['detected_initial']) for r in rows)
        for label,k,n in zip(PROB,values[1:],values):
            lower,upper=interval(k,n) if n else (None,None)
            record.update({label+'_p':k/n if n else None,label+'_low':lower,label+'_high':upper})
        summary.append(record)
    write_csv(path/'end_to_end_probabilities.csv',summary)
    outcomes=[r for name in NAMES for r in read_csv(path/f'{name}-blind.csv')]
    write_csv(path/'blind_recovery.csv',outcomes)
    fig, axes=plt.subplots(1,3,figsize=(12,3.7),layout='constrained',sharey=True)
    for i,site in enumerate(NAMES):
        for grade,axis in zip(PROB,axes):
            rows=[r for r in summary if r['site']==site and r['arm']=='ls_deep' and
                  r['environment']=='all' and r[grade+'_p'] is not None and float(r['g_lo'])>0]
            x=np.array([(float(r['g_lo'])+float(r['g_hi']))/2 for r in rows])+(i-1)*.055
            y=np.array([r[grade+'_p'] for r in rows])
            low=np.array([r[grade+'_low'] for r in rows])
            high=np.array([r[grade+'_high'] for r in rows])
            axis.errorbar(x,y,yerr=np.maximum(0,[y-low,high-y]),fmt='o',ms=3,capsize=2,
                          label=site.replace('_',' '))
            axis.set_ylim(-.05,1.05)
            axis.set_xlabel(r'Injected $g_0$')
            axis.set_title({'detected':'New source detection', 'psf_given_detected':'PSF among new sources',
                            'selected_given_psf':'Search cuts among PSF sources'}[grade])
    axes[0].set_ylabel('Conditional fraction')
    axes[0].legend(frameon=False,fontsize=8)
    save(fig,path,'native_response')


if __name__ == '__main__':
    run(Path('results/v13/image_response'))
