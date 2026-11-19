"""Summarize measured reference sensitivity and the frozen image-generation scope."""
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    root=Path('results/v14/repeat_full');out=root/'ps1_reference_audit'
    reference=out/'reference_stage_counts.csv';population=root/'population_audit/population_stamp_and_support.csv'
    rows=read_csv(reference);faint=[];comparisons=[]
    for site in sorted({r['site'] for r in rows}):
        held=[r for r in rows if r['site']==site and r['split']=='heldout'
              and float(r['g_lo'])>=22.5 and float(r['g_hi'])<=24]
        for variant in sorted({r['reference_variant'] for r in held}):
            sample=[r for r in held if r['reference_variant']==variant]
            n=sum(int(r['references']) for r in sample);k=sum(int(r['selected']) for r in sample)
            faint.append(dict(site=site,reference_variant=variant,g_lo=22.5,g_hi=24,n=n,selected=k,
                fraction=k/n if n else None,
                n_color_ge0p8=sum(int(r['references']) for r in sample if r['color_lo']=='0.8')))
        base={(r['g_lo'],r['color_lo']):r for r in held if r['reference_variant']=='ordinary_psf'}
        tight={(r['g_lo'],r['color_lo']):r for r in held if r['reference_variant']=='psf_tight_shape'}
        keys=[k for k in base if k in tight and int(base[k]['references'])>=20 and int(tight[k]['references'])>=20]
        n=sum(int(base[k]['references']) for k in keys)
        if n:
            base_rate=sum(int(base[k]['references'])*float(base[k]['p_selected']) for k in keys)/n
            tight_rate=sum(int(base[k]['references'])*float(tight[k]['p_selected']) for k in keys)/n
            comparisons.append(dict(site=site,common_supported_bins=len(keys),base_n_in_common_bins=n,
                base_fraction=base_rate,tight_fraction_standardized_to_base_bins=tight_rate,
                difference=tight_rate-base_rate,
                scope='Nested reference subsets, descriptive sensitivity only; no independent-sample significance or identified contamination fraction.'))
    write_csv(out/'faint_heldout_summary.csv',faint)
    write_csv(out/'common_bin_shape_sensitivity.csv',comparisons)
    values=[]
    for r in read_csv(population):
        if r['site']!='v14_south_response_1':continue
        fraction=float(r['eligible_light_before_stamp'])/float(r['full_IMF_light_proxy'])
        values.append(dict(trial=r['trial'],rh_pc=r['rh_pc'],target_MV_proxy=r['target_MV_proxy'],
            realized_MV_proxy=r['realized_MV_proxy'],fraction_proxy_light_magnitude_eligible=fraction,
            unrendered_faint_proxy_light_fraction=1-fraction,
            scope='Magnitude-generation cut only, before spatial truncation; not a measured recovery bias.'))
    write_csv(root/'population_audit/magnitude_generation_light_audit.csv',values)
    missing=[r['unrendered_faint_proxy_light_fraction'] for r in values]
    write_json(root/'scope_diagnostics.json',dict(inputs={str(p):sha(p) for p in (reference,population)},
        code_sha256=sha(Path(__file__)),unique_population_draws=len(values),
        unrendered_faint_proxy_light_fraction_min_median_max=np.quantile(missing,[0,.5,1]).tolist(),
        scope='Aggregate real-data and deterministic-population diagnostics. The Gaia-reference stratum supplies no faint blue-star truth calibration here; shape strata do not identify LS contamination. The original generation limit represents 68–94% of full IMF V-proxy light before spatial truncation; missing diffuse-light effects on source detection/classification need a bounded image check before an unrestricted physical-completeness claim. Do not renormalize target luminosity or change the frozen 144 trials after viewing outcomes. No PS1 physical Pdet, gain interval or new-system promotion.'))


if __name__=='__main__':run()
