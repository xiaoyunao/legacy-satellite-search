"""Draw the first-round aggregate figures from reviewed result tables."""
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np

from .run import read_csv


def figures(base, out):
    out.mkdir(parents=True, exist_ok=True)
    probe = base/'bootes_schema_probe.json'
    if probe.exists():
        flow = json.loads(probe.read_text())['cutflow']
        keys = ('raw', 'valid_G', 'snr_G', 'mag_G', 'valid_R', 'snr_R', 'mag_R',
                'exclude_bit_19', 'area', 'psf')
        names = ('All', 'Valid g', 'g S/N', 'g₀ cut', 'Valid r', 'r S/N', 'r₀ cut',
                 'Maskbits', 'Usable area', 'PSF')
        fig, ax = plt.subplots(figsize=(8, 4.6), layout='constrained')
        counts = [flow[k] for k in keys]
        bars = ax.barh(names, counts, color='#1b6ca8')
        ax.bar_label(bars, labels=[f'{n:,}' for n in counts], padding=3)
        ax.invert_yaxis()
        ax.set(xlim=(0, 1.13*max(counts)), xlabel='Catalog sources', title='Boötes I core · DR11 south gr')
        fig.savefig(out/'bootes_core_cutflow.png', dpi=160)
        plt.close(fig)

    field_path = base/'field_conditions.csv'
    if field_path.exists():
        rows = read_csv(field_path)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
        ax = axes[0]
        symbols = {'pilot_dev': ('o', '#1b6ca8'), 'pilot_eval': ('s', '#c15338'),
                   'deep_control': ('^', '#289567'), 'recovery': ('*', '#7756a8'),
                   'recovery_evaluation': ('*', '#474747'), 'compact': ('D', '#b38320')}
        for role, (marker, color) in symbols.items():
            fields = [r for r in rows if r['role'] == role and r['depth'] == 'base']
            if not fields:
                continue
            ax.scatter([float(r['ra_deg']) for r in fields], [float(r['dec_deg']) for r in fields],
                       s=[30+8*float(r['area_deg2']) for r in fields],
                       marker=marker, color=color, label=role.replace('_', ' '))
        ax.set(xlabel='ICRS RA (deg)', ylabel='ICRS Dec (deg)', xlim=(360, 0), ylim=(-75, 75),
               title='Analysed fields')
        ax.legend(loc='best', fontsize=8)
        ax = axes[1]
        displayed = [r for r in rows if r['depth'] == 'base']
        base_order = [r['field'] for r in displayed]
        xx = np.arange(len(displayed))
        for depth, offset, color in [('base', -.16, '#1b6ca8'), ('deep', .16, '#c15338')]:
            values = {r['field']: r for r in rows if r['depth'] == depth}
            valid = [i for i, field in enumerate(base_order) if field in values]
            ratio = []
            for i in valid:
                r = values[base_order[i]]
                a, b = float(r['n_psf_faint']), float(r['n_non_psf_faint'])
                ratio.append(b / (a + b) if a + b else np.nan)
            ax.bar(xx[valid]+offset, ratio, width=.31, color=color, label=depth)
        ax.set(xticks=xx, xticklabels=base_order, ylabel='Non-PSF fraction at g₀ > 22.5',
               title='Faint source morphology')
        ax.tick_params(axis='x', rotation=50)
        ax.legend()
        fig.savefig(out/'field_conditions.png', dpi=160)
        plt.close(fig)

    path = base/'method_comparison.csv'
    if path.exists():
        all_rows = read_csv(path)
        rows = [r for r in all_rows if r['evaluation_peaks_per_deg2']]
        if rows:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), layout='constrained')
            ax = axes[0]
            for i, r in enumerate(rows):
                n = float(r['evaluation_peaks_per_deg2'])
                lo, hi = (float(r[k]) for k in ('count_interval95_low', 'count_interval95_high'))
                ax.errorbar(i, n, yerr=[[n-lo], [hi-n]], fmt='o', ms=6,
                            color='#1b6ca8' if r['method'] == 'A' else '#c15338', capsize=4)
                ax.plot([i-.24, i+.24], [float(r['budget_per_deg2'])]*2, color='0.5', lw=1.2)
            labels = [f"{r['method']} {r['depth']}\n{r['budget_per_deg2']}" for r in rows]
            ax.set(xticks=np.arange(len(rows)), xticklabels=labels, ylim=(0, None),
                   ylabel='Retained peaks per effective deg²', title='Held-out review density')
            ax.tick_params(axis='x', labelsize=8)
            ax = axes[1]
            for i, r in enumerate(rows):
                n = int(r['benchmark_recovered'])
                den = int(r['benchmark_eligible'])
                ax.bar(i, n, color='#1b6ca8' if r['method'] == 'A' else '#c15338', alpha=.9)
                ax.text(i, n+.06, f'{n}/{den}', ha='center', fontsize=9)
            ax.set(xticks=np.arange(len(rows)), xticklabels=labels, ylabel='Recovered systems',
                   ylim=(0, max(int(r['benchmark_eligible']) for r in rows)+.5),
                   title='Recovery at development-calibrated cuts')
            ax.tick_params(axis='x', labelsize=8)
            fig.savefig(out/'method_comparison.png', dpi=160)
            plt.close(fig)

    path = base/'injection_summary.csv'
    if path.exists():
        rows = read_csv(path)
        keep = [r for r in rows if float(r['budget_per_deg2']) == .3 and int(r['evaluated_trials'])]
        fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True, layout='constrained')
        for ax, distance in zip(axes, ('50', '100')):
            for method, c, offset in [('A', '#1b6ca8', -.14), ('B', '#c15338', .14)]:
                pos, y, elo, ehi = [], [], [], []
                for r in keep:
                    if r['method'] != method or r['distance_kpc'] != distance:
                        continue
                    pos.append([(0,5),(6,11),(12,20),(21,32)].index(
                        (int(r['used_member_min']), int(r['used_member_max']))) + offset)
                    y.append(float(r['fraction']))
                    elo.append(y[-1]-float(r['conditional_binomial_lo']))
                    ehi.append(float(r['conditional_binomial_hi'])-y[-1])
                if pos:
                    ax.errorbar(pos, y, yerr=[elo, ehi], fmt='o', color=c, capsize=3, label=method)
            ax.set(xticks=range(4), xticklabels=['0–5', '6–11', '12–20', '21–32'], ylim=(-.05,1.09),
                   xlabel='Injected members entering search', title=f'{distance} kpc · rₕ = 20 pc')
            ax.legend()
        axes[0].set_ylabel('Conditional recovery fraction')
        fig.savefig(out/'conditional_injections.png', dpi=160)
        plt.close(fig)


if __name__ == '__main__':
    figures(Path('results/summary'), Path('results/figures'))
