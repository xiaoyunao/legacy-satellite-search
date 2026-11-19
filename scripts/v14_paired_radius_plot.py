"""Display actual fixed-population native size-response stages and paired uncertainty."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    folder = Path('results/v14/paired_radius')
    source, summary = folder/'full_stage_pairs.csv', folder/'stage_comparison.csv'
    rows, stats = read_csv(source), read_csv(summary)
    if len(rows) != 48 or len(stats) != 12:
        raise ValueError('Complete24native/48paired-depth experiment required')
    stages = ('initial', 'final', 'psf', 'used', 'cmd')
    labels = ('Initial*', 'Final', 'PSF', 'Hard cuts', 'CMD')
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.7))
    for ax, arm, title in zip(axes[:2], ('ls_base', 'ls_deep'), ('LS baseline', 'LS deeper')):
        selected = {r['stage']:r for r in stats if r['arm']==arm}
        for prefix, color, marker, label in (
                ('parent10', '#286090', 'o', '10 pc parent'),
                ('paired3', '#bd602d', 's', 'Same stars at 3 pc')):
            values = [100*float(selected[s][prefix+'_mean_rendered_fraction']) for s in stages]
            ax.plot(range(5), values, color=color, marker=marker, label=label, linewidth=1.3, markersize=4)
        ax.set_title(title, fontsize=11); ax.set_ylim(0, 40)
        ax.set_ylabel('Mean fraction of rendered members (%)', fontsize=9)
        ax.set_xticks(range(5), labels, rotation=25, ha='right', fontsize=9)
        ax.grid(axis='y', alpha=.15)
    axes[0].legend(frameon=False, fontsize=8)
    ax = axes[2]
    for arm, color, label, offset in (('ls_base', '#286090', 'Baseline', -.06),
                                    ('ls_deep', '#bd602d', 'Deeper', .06)):
        selected = {r['stage']:r for r in stats if r['arm']==arm}
        x = np.arange(5)+offset
        y = [100*float(selected[s]['paired3_minus_parent10_mean_rendered_fraction']) for s in stages]
        low = [100*float(selected[s]['exploratory_paired_bootstrap_low']) for s in stages]
        high = [100*float(selected[s]['exploratory_paired_bootstrap_high']) for s in stages]
        ax.vlines(x, low, high, color=color, linewidth=1.5)
        ax.scatter(x, y, color=color, s=16, label=label)
    ax.axhline(0, color='#666666', linewidth=.8, linestyle='--')
    ax.set_title('Paired difference: 3 pc minus 10 pc', fontsize=10)
    ax.set_ylabel('Percentage points (exploratory 95% interval)', fontsize=9)
    ax.set_xticks(range(5), labels, rotation=25, ha='right', fontsize=9)
    ax.grid(axis='y', alpha=.15); ax.legend(frameon=False, fontsize=8, loc='lower right')
    fig.suptitle('Same rendered stellar populations: native-image response at 100 kpc', fontsize=12, y=.97)
    fig.text(.5, .045, 'Eight shared IMF populations × three fixed skies; gr exposure >99.9% in both sizes. No blind-search P(det) measured.\n'
             '*Final includes iterative detections and is not a subset of Initial. Intervals resample shared populations and selected backgrounds.',
             ha='center', fontsize=8)
    fig.subplots_adjust(left=.055, right=.99, top=.85, bottom=.27, wspace=.34)
    output = folder/'fixed_population_size_response.png'; fig.savefig(output, dpi=180); plt.close(fig)
    backgrounds = []
    for site in sorted({r['site'] for r in rows}):
        for arm in ('ls_base', 'ls_deep'):
            chosen = [r for r in rows if r['site']==site and r['arm']==arm]
            for stage in ('exposed', *stages):
                record = dict(site=site, arm=arm, stage=stage, shared_populations=len(chosen))
                for variant in ('parent10', 'paired3'):
                    record[variant+'_count'] = sum(int(r[variant+'_N_'+stage]) for r in chosen)
                    record[variant+'_mean_rendered_fraction'] = np.mean([
                        int(r[variant+'_N_'+stage])/int(r[variant+'_N_rendered']) for r in chosen])
                backgrounds.append(record)
    write_csv(folder/'stage_by_background.csv', backgrounds)
    neighbors = []
    for site in sorted({r['site'] for r in rows}):
        chosen = [r for r in rows if r['site']==site and r['arm']=='ls_base']
        for kind in ('member', 'blank'):
            record = dict(site=site, neighbor=kind, radius_arcsec=.8, shared_populations=len(chosen))
            for variant in ('parent10', 'paired3'):
                key = variant+'_N_'+kind+'_neighbor_lt0p8arcsec'
                record[variant+'_count'] = sum(int(r[key]) for r in chosen)
                record[variant+'_mean_rendered_fraction'] = np.mean([
                    int(r[key])/int(r[variant+'_N_rendered']) for r in chosen])
            neighbors.append(record)
    write_csv(folder/'neighbor_comparison.csv', neighbors)
    inputs = [source, summary]
    bounds_path = folder/'association_bounds.csv'
    if bounds_path.is_file():
        bounds = read_csv(bounds_path); core_path = folder/'core_source_counts.csv'
        cores = read_csv(core_path); pooled = []; pooled_core = []
        for arm in ('ls_base', 'ls_deep'):
            for variant in ('parent10', 'paired3'):
                for radius in (.4, .8, 1.6):
                    selected = [r for r in bounds if r['arm']==arm and r['variant']==variant
                                and float(r['radius_arcsec'])==radius]
                    if len(selected)!=24: raise ValueError('Association audit incomplete')
                    record = dict(arm=arm, variant=variant, radius_arcsec=radius, native_cases=24)
                    for key in ('greedy_final_at0p8', 'maximum_final', 'greedy_psf_at0p8',
                                'maximum_psf', 'greedy_used_at0p8', 'maximum_used'):
                        record[key] = sum(int(r[key]) for r in selected)
                    pooled.append(record)
                selected = [r for r in cores if r['arm']==arm and r['variant']==variant]
                if len(selected)!=24: raise ValueError('Core-count audit incomplete')
                record = dict(arm=arm, variant=variant, native_cases=24, core_radius_in_rh=3)
                for key in ('catalogue_sources', 'blank_sources', 'catalogue_minus_blank',
                            'novel_sources', 'novel_PSF', 'novel_hard'):
                    record[key] = sum(int(r[key]) for r in selected)
                pooled_core.append(record)
        write_csv(folder/'association_summary.csv', pooled)
        write_csv(folder/'core_source_summary.csv', pooled_core)
        inputs.extend([bounds_path, core_path])
    write_json(folder/'figure_manifest.json', dict(inputs={str(p):sha(p) for p in inputs},
        code_sha256=sha(Path(__file__)), figure_sha256=sha(output),
        scope='Conditional finite rendered populations; mean fractions weight realization/background pairs equally. '
              'Differences preserve radius/depth/population pairing. Eight populations and three selected skies '
              'do not support broad-sky confidence. Shrinking changes local coverage, dust, foreground blends '
              'and source-noise pixels as well as mutual proximity. Neighbor counts are geometry diagnostics, '
              'not causal decomposition. Initial/final products need not be nested. No blind-search recovery '
              'or calibratedV/full spatial selection function is inferred.'))
    print(output)


if __name__ == '__main__':
    run()
