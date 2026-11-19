"""Plot real held-out PS1 selection diagnostics, conditional on LS reference proxies."""
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v12_selection_stats import interval


def run():
    out=Path('results/v14/repeat/ps1_response');path=out/'selection_stage_counts.csv'
    input_checksum=sha(path)
    grouped=defaultdict(list)
    for r in read_csv(path):
        if r['split']=='heldout':grouped[r['site'],float(r['ls_g_lo']),float(r['ls_g_hi'])].append(r)
    rows=[]
    for (site,lo,hi),values in sorted(grouped.items()):
        n=sum(int(r['references']) for r in values)
        counts={k:sum(int(r[k]) for r in values) for k in ('primary','gr','i_valid','i_snr','morphology','selected')}
        if not all(0<=counts[k]<=n for k in counts):raise ValueError('Invalid stage count')
        bounds=interval(counts['selected'],n) if n else (None,None)
        rows.append(dict(site=site,g_lo=lo,g_hi=hi,references=n,**counts,
                         final_fraction=counts['selected']/n if n else None,lo=bounds[0],hi=bounds[1]))
    write_csv(out/'heldout_magnitude_summary.csv',rows)
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    sites=sorted({r['site'] for r in rows});colors=['#34618d','#b6552e','#52806b']
    for site,color in zip(sites,colors):
        subset=[r for r in rows if r['site']==site and r['references']>=20 and r['g_lo']>=20 and r['g_hi']<=24]
        x=[(r['g_lo']+r['g_hi'])/2 for r in subset];y=np.array([r['final_fraction'] for r in subset])
        axes[0].errorbar(x,y,yerr=[y-np.array([r['lo'] for r in subset]),np.array([r['hi'] for r in subset])-y],
                         marker='o',ms=4,lw=1,color=color,label=site.replace('v14_south_response_','Site '))
        faint=[r for r in rows if r['site']==site and r['g_lo']>=23 and r['g_hi']<=24]
        n=sum(r['references'] for r in faint)
        vals=[sum(r[k] for r in faint)/n for k in ('primary','gr','i_snr','morphology','selected')]
        axes[1].plot(range(5),vals,marker='o',color=color)
    axes[0].set(xlabel='Reference LS g₀ (mag)',ylabel='PS1 final selection / LS proxies',ylim=(0,1.03))
    axes[0].legend(fontsize=9);axes[0].set_title('Held-out sources · exact binomial intervals')
    axes[1].set_xticks(range(5),['Primary','gr S/N','i S/N','i shape','Final'],rotation=25)
    axes[1].set(ylabel='Fraction of LS proxies',ylim=(0,1.03),title='Reference 23 ≤ g₀ < 24 · cumulative stages')
    fig.suptitle('PS1 selection conditional on ordinary LS point-source proxies',fontsize=12)
    for suffix in ('png','pdf','svg'):
        path=out/f'heldout_ps1_response.{suffix}'
        fig.savefig(path,dpi=150)
        if suffix=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)
    write_json(out/'figure_manifest.json',dict(input_sha256=input_checksum,
        scope='Real held-out matched-source diagnostics; not a physical satellite completeness curve. Colour distributions vary by site. Binomial intervals omit sky-to-sky and reference-classification systematics.'))


if __name__=='__main__':run()
