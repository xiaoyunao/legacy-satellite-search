"""Accept four real PS1 condition probes and plot descriptive source-sampled spreads."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ls_satsearch.run import read_csv,sha,write_csv,write_json


def run(root):
    manifest=root/'manifest.json';table=root/'source_sampled_conditions.csv';d=json.loads(manifest.read_text())
    config=Path('configs/v14_repeat/ps1_conditions.yaml');code=Path('scripts/v14_ps1_conditions.py')
    if d['config_sha256']!=sha(config) or d['code_sha256']!=sha(code):raise ValueError('Actual condition-probe policy/code changed')
    expected={'cosmos_local_control',*(f'v14_south_response_{i}' for i in (1,2,3))}
    if {r['site'] for r in d['fields']}!=expected or any(r['state']!='acquired_and_measured' for r in d['fields']):raise ValueError('Four-field acquisition incomplete')
    if any(abs(c['median_mag_minus_flux_AB'])>.02 for r in d['fields'] for c in r['unit_checks'].values() if c['n']>=20):raise ValueError('PS1 Jy/AB relation failed')
    rows=read_csv(table);selected=[r for r in rows if r['radial_low_arcmin']=='3' and r['observed_mag_low']=='22']
    control={(r['sample'],r['band']):r for r in selected if r['site']=='cosmos_local_control'}
    comparison=[]
    for r in selected:
        c=control[r['sample'],r['band']]
        delta=float(c['formal_observed_m5_median'])-float(r['formal_observed_m5_median']) if c['formal_observed_m5_median'] and r['formal_observed_m5_median'] else None
        comparison.append(dict(r,COSMOS_minus_site_formal_observed_m5=delta))
    write_csv(root/'fixed_stratum_comparison.csv',comparison)
    fig,axes=plt.subplots(1,3,figsize=(12.8,4.3),layout='constrained')
    names={'cosmos_local_control':'COSMOS local','v14_south_response_1':'Background 1','v14_south_response_2':'Background 2','v14_south_response_3':'Background 3'}
    colors={'cosmos_local_control':'#d95f0e','v14_south_response_1':'#2c7fb8','v14_south_response_2':'#41ab5d','v14_south_response_3':'#756bb1'}
    for ax,band in zip(axes,'gri'):
        for r in selected:
            if r['sample']!='all_primary' or r['band']!=band or r['formal_noise_count_supported']!='True':continue
            x=float(r['PSF_FWHM_arcsec_median']);y=float(r['formal_observed_m5_median'])
            ax.errorbar(x,y,xerr=[[x-float(r['PSF_FWHM_arcsec_p16'])],[float(r['PSF_FWHM_arcsec_p84'])-x]],yerr=[[y-float(r['formal_observed_m5_p16'])],[float(r['formal_observed_m5_p84'])-y]],marker='*' if r['site']=='cosmos_local_control' else 'o',ms=10 if r['site']=='cosmos_local_control' else 6,color=colors[r['site']],capsize=2,label=names[r['site']])
        ax.set(title=band,xlabel='Catalogue PSF FWHM (arcsec)',ylabel='Formal source-error m₅ (AB observed)');ax.grid(alpha=.2)
    axes[0].legend(fontsize=8,loc='best')
    fig.suptitle('Local PS1 DR2 conditions: observed m=22–23, 3–20′; marginal source spreads, not confidence intervals',fontsize=11)
    fig.savefig(root/'local_conditions.png',dpi=170);plt.close(fig)
    write_json(root/'acceptance.json',dict(job=d['job'],inputs={str(p):sha(p) for p in (manifest,table,config,code)},summary_code_sha256=sha(Path(__file__)),four_fields_and_units_passed=True,valid_stack_positions=sum(r['primary_sources'] for r in d['fields']),discarded_split_primary_rows=sum(r['discarded_split_primary_rows'] for r in d['fields']),discarded_invalid_stack_positions=sum(r['invalid_stack_positions'] for r in d['fields']),physical_PS1_transfer_validated=False,scope='Descriptive local PS1 condition/noise proxies. Catalogue PSF flux errors are not independently calibrated aperture noise or stellar completeness; source-selected distributions and percentile spreads are not independent-sky uncertainty. Compare all three bands; the bright-i point-proxy i22–23 stratum is empty by construction, not absent exposure. COSMOS local gr error proxies differ from the three physical backgrounds, while i is closer. Do not transfer a universal response, make a scalar depth-offset correction, infer system Pdet or claim the entire COSMOS control has these local conditions.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);run(**vars(p.parse_args()))
