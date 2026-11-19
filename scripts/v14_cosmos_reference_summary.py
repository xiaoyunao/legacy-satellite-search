"""Validate and plot aggregate independent-reference results; never load source rows locally."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta

from ls_satsearch.run import read_csv,sha,write_csv,write_json


def run(source,output):
    output.mkdir(parents=True,exist_ok=True)
    manifest=source/'validation.json';saved=json.loads(manifest.read_text())
    response=source/'independent_stellar_source_response.csv';composition=source/'LS_proxy_reference_composition.csv';held=source/'heldout_estimator_validation.csv'
    inputs={str(p):sha(p) for p in (manifest,response,composition,held)}
    rows=read_csv(response);mix=read_csv(composition);tests=read_csv(held)
    total=sum(int(r['references']) for r in rows if r['context']=='all' and r['population']=='all_colors')
    if total!=saved['morphology_SED_stellar_references']:raise ValueError('Reference partition does not reproduce parent')
    faint=sum(int(r['references']) for r in rows if r['context']=='all' and r['population']=='blue_HSC_observed' and 22.5<=float(r['HSC_observed_g_low'])<24.5)
    if faint!=saved['blue_faint_stellar_references']:raise ValueError('Faint-blue partition changed')
    for r in mix:
        if sum(int(r[k]) for k in ('independent_stellar_references','independent_resolved_SED_galaxies','ambiguous_or_unmatched'))!=int(r['proxy_sources']):raise ValueError('Composition labels do not partition proxy sample')
    blue=[]
    for low in (22.,22.5,23.,23.5,24.):
        cells=[r for r in mix if float(r['LS_g0_low'])==low and float(r['LS_gr0_high'])==.4]
        counts={key:sum(int(r[key]) for r in cells) for key in ('proxy_sources','independent_stellar_references','independent_resolved_SED_galaxies','ambiguous_or_unmatched','PS1_selected','PS1_selected_stellar_references')}
        n=counts['proxy_sources'];blue.append(dict(LS_g0_low=low,LS_g0_high=float(cells[0]['LS_g0_high']),**counts,galaxy_label_fraction_lower=counts['independent_resolved_SED_galaxies']/n if n else None))
    write_csv(output/'blue_proxy_composition.csv',blue)
    # Bonferroni 97.5% marginal bounds give conservative 95% per-cell
    # difference bounds, conditional on binomial reference-count assumptions.
    def marginal(k,n):
        return (float(beta.ppf(.0125,k,n-k+1)) if k else 0.,
                float(beta.ppf(.9875,k+1,n-k)) if k<n else 1.)
    uncertain=[]
    for test in tests:
        if test['supported']!='True':continue
        cells={r['split']:r for r in mix if all(r[k]==test[k] for k in ('LS_g0_low','LS_g0_high','LS_gr0_low','LS_gr0_high'))}
        train=cells['train'];heldout=cells['heldout']
        n=int(train['proxy_sources']);k=int(train['PS1_selected']);nt=int(heldout['independent_stellar_references']);kt=int(heldout['PS1_selected_stellar_references'])
        lo,hi=marginal(k,n);lt,ht=marginal(kt,nt)
        uncertain.append(dict(test,train_proxy_selected=k,heldout_stellar_selected=kt,
            conditional_reference_MC_difference_low=lo-ht,conditional_reference_MC_difference_high=hi-lt,
            interval_scope='Conservative95% per-cell count interval; not sky/reference-label/transport uncertainty or simultaneous coverage across all tested cells.'))
    write_csv(output/'heldout_estimator_uncertainty.csv',uncertain)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    selected=[r for r in rows if r['context']=='all' and r['split']=='heldout' and r['population']=='blue_HSC_observed' and 22.<=float(r['HSC_observed_g_low'])<24.5]
    x=np.array([(float(r['HSC_observed_g_low'])+float(r['HSC_observed_g_high']))/2 for r in selected])
    for key,label,color,shift in [('ls_base','LS baseline','#2c7fb8',-.035),('ls_deep','LS deeper','#41ab5d',0),('selected','PS1 DR2 joint','#d95f0e',.035)]:
        y=np.array([float(r[key+'_joint_fraction']) for r in selected]);lo=np.array([float(r[key+'_reference_binomial_low']) for r in selected]);hi=np.array([float(r[key+'_reference_binomial_high']) for r in selected])
        axes[0].errorbar(x+shift,y,yerr=[np.maximum(y-lo,0),np.maximum(hi-y,0)],label=label,color=color,marker='o',capsize=2,lw=1)
    for xx,r in zip(x,selected):axes[0].text(xx,1.08,'n='+r['references'],ha='center',fontsize=8)
    axes[0].set(xlabel='Observed HSC g (independent reference)',ylabel='Selected / labelled stellar references',ylim=(-.02,1.17),title='Held-out HSC blue references: −0.2 ≤ g−r < 0.6')
    axes[0].legend(fontsize=9,loc='lower left');axes[0].grid(alpha=.2)
    plot=blue[:-1];x=np.arange(len(plot));bottom=np.zeros(len(plot))
    for key,label,color in [('independent_stellar_references','Stellar reference','#41ab5d'),('independent_resolved_SED_galaxies','Resolved + SED galaxy','#d95f0e'),('ambiguous_or_unmatched','Unknown / unmatched','#bdbdbd')]:
        f=np.array([r[key]/r['proxy_sources'] for r in plot]);axes[1].bar(x,f,bottom=bottom,label=label,color=color);bottom+=f
    for xx,r in zip(x,plot):axes[1].text(xx,1.02,'n='+str(r['proxy_sources']),ha='center',fontsize=8)
    axes[1].set(xticks=x,xticklabels=[f"{r['LS_g0_low']:g}–{r['LS_g0_high']:g}" for r in plot],xlabel='Extinction-corrected LS g₀ bins',ylabel='Fraction of LS ordinary PSF proxies',ylim=(0,1.14),title='LS blue proxies: (g−r)₀ < 0.4; labels are conditional')
    axes[1].legend(fontsize=8,loc='lower left')
    fig.suptitle(f"Independent external reference: {saved['common_reference_control_deg2']:.3f} deg²; source response, not system completeness",fontsize=12)
    fig.savefig(output/'reference_response.png',dpi=170);plt.close(fig)
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Aggregate parent changed during summary')
    write_json(output/'acceptance.json',dict(inputs=inputs,code_sha256=sha(Path(__file__)),reference_partition_verified=True,composition_partition_verified=True,stellar_references=total,faint_blue_stellar_references=faint,supported_estimator_bins=sum(r['supported']=='True' for r in tests),supported_LS_blue_estimator_bins=sum(r['supported']=='True' and float(r['LS_gr0_high'])==.4 for r in tests),physical_PS1_transfer_validated=False,scope='Conditional independent-label source audit in one exposure-defined field. Exact marginal binomial intervals and conservative Bonferroni difference bounds describe finite reference counts, not sky/reference-label/matching/transport systematics or paired differences. HSC observed and LS corrected bins use distinct native passbands; do not equate them. Unknown references stay unknown; galaxy-labelled fractions are reference-conditional lower labels, not globally calibrated contamination. No physical LS−PS1 Pdet, new discovery area, candidate confirmation or population constraint.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    run(**vars(parser.parse_args()))
