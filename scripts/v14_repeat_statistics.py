"""Summarize the accepted 144 CCD trials, retaining shared populations and scope."""
from collections import defaultdict
from importlib.metadata import version
import json
from pathlib import Path
import statistics

import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np
from scipy.stats import binomtest
import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json

ROOT = Path('results/v14/repeat_full')
ANALYSIS = Path('configs/v14_repeat/analysis.yaml')


def interval(k, n, level=.95):
    result = binomtest(k, n).proportion_ci(confidence_level=level, method='exact')
    return float(result.low), float(result.high)


def resample(delta, draws, seed):
    """Shape: background × shared repetition block × physical cell."""
    rng = np.random.default_rng(seed)
    n_backgrounds, n_blocks, n_cells = delta.shape
    backgrounds = rng.integers(n_backgrounds, size=(draws, n_backgrounds))
    blocks = rng.integers(n_blocks, size=(draws, n_blocks))
    selected = delta[backgrounds[:, :, None, None], blocks[:, None, :, None],
                     np.arange(n_cells)[None, None, None, :]]
    return selected.mean(axis=(1, 2))


def simultaneous_paired_bound(delta, level=.95):
    """Bonferroni exact marginal bounds; shared backgrounds need not be independent."""
    n_backgrounds, n_blocks, n_cells = delta.shape
    marginal_level = 1-(1-level)/(2*n_backgrounds*n_cells)
    low, high = np.zeros((n_backgrounds, n_cells)), np.zeros((n_backgrounds, n_cells))
    for site in range(n_backgrounds):
        for cell in range(n_cells):
            values = delta[site, :, cell]
            win = interval(int((values == 1).sum()), n_blocks, marginal_level)
            loss = interval(int((values == -1).sum()), n_blocks, marginal_level)
            low[site, cell], high[site, cell] = win[0]-loss[1], win[1]-loss[0]
    return low, high


def cell_diagnostics(rows, stages, out):
    cells=[]
    for rh in (3,10,30):
        for mv in (-3,-1.5):
            for arm in ('ls_base','ls_deep'):
                chosen=[r for r in rows if float(r['rh_pc'])==rh
                        and float(r['expected_MV_proxy'])==mv and r['arm']==arm]
                unique={r['latent_population_id']:r for r in chosen}
                record=dict(rh_pc=rh,target_MV_proxy=mv,arm=arm,backgrounds=3,
                    unique_populations=len(unique),background_trials=len(chosen),
                    spatial_detected=sum(r['spatial']=='True' for r in chosen),
                    highest_DM_correct=sum(r['blind_correct']=='True' for r in chosen))
                record.update({key+'_mean':statistics.mean(float(r[key]) for r in chosen)
                    for key in ('N_rendered','N_exposed','N_final','N_psf','N_used','N_cmd_at_truth_dm')})
                record.update(realized_MV_min=min(float(r['realized_MV_proxy']) for r in unique.values()),
                    realized_MV_max=max(float(r['realized_MV_proxy']) for r in unique.values()))
                for a,b in (('detected','exposed'),('PSF','detected'),('hard_selected','PSF')):
                    ratios=[float(r['L_proxy_'+a])/float(r['L_proxy_'+b]) for r in chosen if float(r['L_proxy_'+b])>0]
                    record[f'mean_true_light_{a}_given_{b}']=statistics.mean(ratios) if ratios else None
                cells.append(record)
    write_csv(out/'physical_cell_summary.csv',cells)
    grouped=defaultdict(lambda:defaultdict(int))
    for row in stages:
        if row['arm']!='ls_base' or float(row['target_MV_proxy'])!=-3 or float(row['g_lo']) not in (20,22,23,23.5):continue
        key=(row['rh_pc'],row['g_lo'],row['g_hi'],row['environment'])
        for name in ('exposed','detected','psf','selected'):grouped[key][name]+=int(row[name])
    neighbour=[]
    for key,counts in sorted(grouped.items(),key=lambda p:(float(p[0][0]),float(p[0][1]),p[0][3])):
        record=dict(zip(('rh_pc','g_lo','g_hi','background_neighbour_stratum'),key))
        record.update(counts,new_match_fraction=counts['detected']/counts['exposed'] if counts['exposed'] else None,
            PSF_given_new_match=counts['psf']/counts['detected'] if counts['detected'] else None)
        neighbour.append(record)
    write_csv(out/'bright_cell_neighbour_diagnostic.csv',neighbour)
    write_json(out/'bright_cell_neighbour_diagnostic.json',dict(
        input_sha256=sha(out/'stage_attrition_by_physical_cell.csv'),
        scope='Diagnostic aggregation of accepted real CCD stages, target V proxy=-3, baseline. Neighbours are pre-existing blank-catalogue sources, not injected mutual neighbours. Fractions are descriptive, not independent-star confidence intervals or a controlled radius effect. New-match loss includes0.8arcsec unique association/blending. Keep actual IMF light and sky conditions.'))


def run():
    acceptance_path = ROOT/'full_acceptance.json'
    acceptance = json.loads(acceptance_path.read_text())
    if not acceptance.get('all_native_and_LS_measurements_accepted'):
        raise ValueError('Complete the full native/LS acceptance gate first')
    summary_path = ROOT/'full_summary.csv'
    if sha(summary_path) != acceptance['summary_sha256']:
        raise ValueError('Accepted summary changed')
    for path, checksum in acceptance['source_sha256'].items():
        if sha(Path(path)) != checksum:
            raise ValueError('Accepted physical evidence changed: '+path)
    analysis = yaml.safe_load(ANALYSIS.read_text())
    rows = read_csv(summary_path)
    sites = sorted({r['site'] for r in rows})
    cells = sorted({(float(r['rh_pc']), float(r['expected_MV_proxy'])) for r in rows})
    lookup = {(r['site'], int(r['trial']), r['arm']): r for r in rows}
    if len(lookup) != 288 or len(rows) != 288 or len(sites) != 3 or len(cells) != 6:
        raise ValueError('Registered paired grid is incomplete')
    metrics = [analysis['primary_endpoint'], *analysis['secondary_endpoints']]
    site_rates, contrasts = [], []
    for metric in metrics:
        arms = {arm: np.zeros((3, 8, 6), dtype=np.int8) for arm in ('ls_base', 'ls_deep')}
        for site_index, site in enumerate(sites):
            for cell_index, (radius, mv) in enumerate(cells):
                for arm in arms:
                    chosen = [r for r in rows if r['site'] == site and r['arm'] == arm
                              and float(r['rh_pc']) == radius and float(r['expected_MV_proxy']) == mv]
                    if len(chosen) != 8 or {int(r['realization_id']) for r in chosen} != set(range(8)):
                        raise ValueError('Shared repetition blocks differ from registration')
                    for row in chosen:
                        arms[arm][site_index, int(row['realization_id']), cell_index] = row[metric] == 'True'
                    count = int(arms[arm][site_index, :, cell_index].sum())
                    low, high = interval(count, 8)
                    site_rates.append(dict(site=site, arm=arm, rh_pc=radius, target_MV_proxy=mv,
                        metric=metric, independent_latent_draws=8, detected=count, p=count/8,
                        fixed_background_MC_low=low, fixed_background_MC_high=high,
                        blank_spatial=sum(r['blank_spatial']=='True' for r in chosen),
                        realized_MV_min=min(float(r['realized_MV_proxy']) for r in chosen),
                        realized_MV_max=max(float(r['realized_MV_proxy']) for r in chosen)))
        delta = arms['ls_deep'] - arms['ls_base']
        draws = resample(delta, analysis['bootstrap_draws'], analysis['seed'])
        conditional_low, conditional_high = simultaneous_paired_bound(delta)
        for cell_index in [None, *range(6)]:
            selection = slice(None) if cell_index is None else slice(cell_index, cell_index+1)
            values = delta[:, :, selection]
            distribution = draws[:, selection].mean(axis=1)
            low, high = np.quantile(distribution, [.025, .975])
            point = float(values.mean())
            contrasts.append(dict(metric=metric, rh_pc='all' if cell_index is None else cells[cell_index][0],
                target_MV_proxy='all' if cell_index is None else cells[cell_index][1],
                backgrounds=3, shared_blocks=8, unique_populations=48 if cell_index is None else 8,
                background_trials=values.size, baseline_detected=int(arms['ls_base'][:, :, selection].sum()),
                deeper_detected=int(arms['ls_deep'][:, :, selection].sum()),
                deeper_only=int((values==1).sum()), baseline_only=int((values==-1).sum()),
                deeper_minus_baseline=point, resampling_p025=float(low), resampling_p975=float(high),
                simultaneous_fixed_background_MC_low=float(conditional_low[:, selection].mean()),
                simultaneous_fixed_background_MC_high=float(conditional_high[:, selection].mean()),
                meets_registered_depth_gain_screen=point>.10 and low>0,
                primary_LS_minus_PS1_conclusion='unresolved_response_validation'))
    out = ROOT/'statistics'
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out/'fixed_background_cell_recovery.csv', site_rates)
    write_csv(out/'paired_depth_resampling.csv', contrasts)
    raw = []
    for site in sites:
        raw.extend(read_csv(Path('results/v14_repeat_full/image_response')/(site+'-blind.csv')))
    stages = []
    for site in sites:
        stages.extend(read_csv(Path('results/v14_repeat_full/image_response')/(site+'-stages.csv')))
    bucket = defaultdict(list)
    for row in stages:
        original = lookup[row['site'], int(row['trial']), row['arm']]
        bucket[(row['site'],row['arm'],original['rh_pc'],original['expected_MV_proxy'],
                row['g_lo'],row['g_hi'],row['environment'])].append(row)
    stage_summary = []
    for key, batch in sorted(bucket.items()):
        if len(batch) != 8:
            raise ValueError('Physical stage stratum lacks eight realizations')
        totals = {name:sum(int(r[name]) for r in batch) for name in
                  ('exposed','detected_initial','detected','psf','selected')}
        stage_summary.append(dict(zip(('site','arm','rh_pc','target_MV_proxy','g_lo','g_hi','environment'),key),
            **totals, independent_latent_draws=8,
            new_detection_fraction=totals['detected']/totals['exposed'] if totals['exposed'] else None,
            PSF_given_detected=totals['psf']/totals['detected'] if totals['detected'] else None,
            hard_selection_given_PSF=totals['selected']/totals['psf'] if totals['psf'] else None))
    write_csv(out/'stage_attrition_by_physical_cell.csv', stage_summary)
    cell_diagnostics(rows,stage_summary,out)
    write_csv(out/'all_trial_diagnostics.csv', raw)
    light_summary=[]
    for row in rows:
        full=float(row['L_proxy_full_IMF']);exposed=float(row['L_proxy_exposed'])
        light_summary.append(dict(site=row['site'],trial=row['trial'],arm=row['arm'],rh_pc=row['rh_pc'],
            target_MV_proxy=row['expected_MV_proxy'],realized_MV_proxy=row['realized_MV_proxy'],
            **{key:float(row[key]) for key in row if key.startswith('L_proxy_')},
            rendered_over_full_IMF=float(row['L_proxy_rendered'])/full if full else None,
            detected_over_exposed_true_light=float(row['L_proxy_detected'])/exposed if exposed else None,
            PSF_over_exposed_true_light=float(row['L_proxy_PSF'])/exposed if exposed else None,
            selected_over_exposed_true_light=float(row['L_proxy_hard_selected'])/exposed if exposed else None))
    write_csv(out/'true_light_attrition.csv',light_summary)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), sharey=True)
    colors = {-3.: '#235e91', -1.5: '#b5542b'}
    for axis, site in zip(axes, sites):
        for mv in (-3., -1.5):
            for arm, marker, offset in (('ls_base','o',.96),('ls_deep','s',1.04)):
                chosen = [r for r in site_rates if r['site']==site and r['arm']==arm
                          and r['target_MV_proxy']==mv and r['metric']=='spatial']
                chosen.sort(key=lambda r:r['rh_pc'])
                y = np.array([r['p'] for r in chosen])
                axis.errorbar(np.array([r['rh_pc'] for r in chosen])*offset, y,
                    yerr=[y-np.array([r['fixed_background_MC_low'] for r in chosen]),
                          np.array([r['fixed_background_MC_high'] for r in chosen])-y],
                    color=colors[mv], linestyle='none', marker=marker, ms=4, capsize=2,
                    label=f'{mv:g} V proxy, '+('baseline' if arm=='ls_base' else 'deeper'))
        axis.set(xscale='log', xticks=[3,10,30], xticklabels=['3','10','30'],
                 xlabel='Sampled circularized radius (pc)', ylim=(-.04,1.04),
                 title=site.removeprefix('v14_south_response_')+' / fixed background')
        axis.grid(alpha=.15)
        axis.xaxis.set_minor_locator(NullLocator())
    axes[0].set_ylabel('Spatial recovery (8 IMF draws per cell)')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.015),ncol=4,fontsize=8,frameon=False)
    fig.suptitle('Matched-budget100 kpc CCD trials; conditional on generation/stamp limits\n3/10 pc target nodes;30 pc boundary control; realized luminosities vary',fontsize=10)
    fig.subplots_adjust(left=.065,right=.99,bottom=.23,top=.80,wspace=.08)
    fig.savefig(out/'conditional_physical_recovery.png', dpi=160)
    plt.close(fig)
    write_json(out/'manifest.json', dict(acceptance_sha256=sha(acceptance_path),
        analysis_sha256=sha(ANALYSIS), code_sha256=sha(Path(__file__)),
        native_trials=144, independent_populations=48, backgrounds=3, arms=2,
        full_PS1_physical_response_validated=False,
        detector_policy_scope=analysis['detector_policy_scope'],
        versions={name:version(name) for name in ('numpy','scipy','matplotlib')},
        scope='Accepted LS CCD measurements only. Target V proxy is not measured V luminosity; each radius has different IMF draws, with realized light retained. Three backgrounds are selected conditions, not a random all-sky sample. Resampling retains common populations across skies/depths; its percentiles are exploratory sky-condition sensitivity. Exact per-cell intervals and simultaneous fixed-background paired bounds retain finite Monte Carlo uncertainty even with zero discordances. Truncation/faint-flux guards and unknown true extraction/classification losses limit population completeness. C/top-three diagnostics do not automatically classify or reject a system. No physical PS1 delta or 50% contour is manufactured.'))
    print('ACCEPTED_144_LS_STATISTICS', len(site_rates), len(contrasts), flush=True)


if __name__ == '__main__':
    run()
