"""Plot the five measured local LS–survey flux-error depth comparisons."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, sha, write_json

ROOT = Path('results/v14/repeat_full')
PS1 = ROOT / 'matched_source_depth'
DECAM = ROOT / 'decam_matched_depth'


def run():
    ps_path = PS1 / 'depth_summary.csv'
    opt_path = DECAM / 'matched_dec_am_depth.csv'
    if (sha(ps_path) != json.loads((PS1 / 'manifest.json').read_text())['outputs'][ps_path.name]
            or sha(opt_path) != json.loads((DECAM / 'manifest.json').read_text())['table_sha256']):
        raise ValueError('Accepted measured depth tables changed')
    ps = [r for r in read_csv(ps_path) if r['selection'] == 'LS_PSF']
    opt = read_csv(opt_path)
    fields = [('PS1 DR2 · CCD ' + r[-1], ps, 'site', r, 'PS1', 'pairs')
              for r in sorted({row['site'] for row in ps})]
    fields.extend((r, opt, 'survey', r, 'external', 'paired_points') for r in ('DES DR2', 'DELVE DR3'))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained', sharex=True, sharey=True)
    for ax, b, color in zip(axes, 'gr', ('#1e6091', '#9b3d30')):
        for i, (_, table, column, group, prefix, count) in enumerate(fields):
            row, = [r for r in table if r[column] == group and r['band'] == b]
            p16, p50, p84 = (float(row[f'paired_LS_minus_{prefix}_m10_{q}'])
                             for q in ('p16', 'median', 'p84'))
            ax.errorbar(p50, i, xerr=np.array([[p50 - p16], [p84 - p50]]), color=color,
                        ms=5, lw=1.4, capsize=3, marker='o')
            ax.annotate(f"{int(row[count]):,}", (1, i), xycoords=('axes fraction', 'data'),
                        xytext=(-5, 7), textcoords='offset points', ha='right', fontsize=8)
        ax.set(yticks=np.arange(len(fields)), yticklabels=[f[0] for f in fields],
               ylim=(len(fields) - .5, -.5), title=f'{b} band',
               xlabel='LS − comparator 10σ depth (mag)')
        ax.axvline(0., color='.4', ls=':', lw=1)
        ax.grid(axis='x', color='.9')
    fig.suptitle('Paired source-noise depth on five local fields\n'
                 'Median and 16th–84th percentiles of matched sources')
    outputs = []
    for suffix in ('png', 'pdf'):
        p = DECAM / f'local_survey_depth_comparison.{suffix}'
        fig.savefig(p, dpi=175)
        outputs.append(p)
    plt.close(fig)
    write_json(DECAM / 'figure_manifest.json', dict(inputs={str(p): sha(p) for p in (ps_path, opt_path)},
        outputs={p.name: sha(p) for p in outputs}, code_sha256=sha(Path(__file__)),
        scope='Matched catalogue flux-error depth, with sample counts at right. Percentile bars describe source-to-source dispersion. These measured fields do not estimate the survey-wide distribution or completeness.'))


if __name__ == '__main__':
    run()
