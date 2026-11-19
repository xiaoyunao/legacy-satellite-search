"""Plot actual saved-peak sensitivity for the single faint-light diagnostic."""
from pathlib import Path

import matplotlib.pyplot as plt

from ls_satsearch.run import read_csv, sha, write_json


def run():
    folder = Path('results/v14/faint_light')
    source = folder/'saved_peak_margins.csv'
    counts = folder/'paired_comparison.csv'
    rows = read_csv(source); paired = read_csv(counts)
    if len(rows) != 12 or len(paired) != 6:
        raise ValueError('Require all three paired backgrounds and both depth arms')
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    for ax, arm, label in zip(axes, ('ls_base', 'ls_deep'), ('LS baseline', 'LS deeper')):
        for variant, color, marker, title, offset in (
                ('extended_bright_control', '#286090', 'o', 'Extended bright control', -.035),
                ('added_faint_light', '#bd602d', 's', '+ faint IMF members', .035)):
            selected = sorted((r for r in rows if r['arm']==arm and r['variant']==variant), key=lambda r:r['site'])
            ax.plot([i+offset for i in range(1, 4)], [float(r['best_matching_group_score']) for r in selected],
                    marker=marker, color=color, linewidth=1, markersize=5, label=title)
        cutoff = float(next(r['cutoff'] for r in rows if r['arm']==arm))
        ax.axhline(cutoff, color='#555555', linestyle='--', linewidth=1, label='Frozen matched-policy cut')
        selected = sorted((r for r in paired if r['arm']==arm), key=lambda r:r['site'])
        for i, row in enumerate(selected, 1):
            old, new = row['extended_bright_control_N_bright_used'], row['added_faint_light_N_bright_used']
            ax.text(i, .025, f'N(hard) {old} → {new}', transform=ax.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=8)
        ax.set_title(label, fontsize=11)
        ax.set_xticks([1, 2, 3], ['Background 1', 'Background 2', 'Background 3'])
        ax.set_xlim(.65, 3.35); ax.grid(axis='y', alpha=.15)
        ax.set_ylabel('Best matching group A statistic (not sigma)')
        lo, hi = ax.get_ylim(); ax.set_ylim(lo-.35, hi+.2)
    axes[0].legend(loc='upper right', fontsize=7, frameon=False)
    fig.suptitle('One near-boundary IMF realization on three fixed backgrounds', fontsize=12, y=.97)
    fig.text(.5, .035, 'Same 278 bright members; +4975 faint stars; 95.9% IMF V-proxy light rendered inside 3.1 arcmin.\n'
             'Conditional faint-position / photon perturbation; original 144 trials unchanged. No global completeness correction.',
             ha='center', fontsize=8)
    fig.subplots_adjust(left=.075, right=.985, bottom=.24, top=.85, wspace=.27)
    output = folder/'faint_light_score_sensitivity.png'
    fig.savefig(output, dpi=180); plt.close(fig)
    write_json(folder/'figure_manifest.json', dict(inputs={str(p):sha(p) for p in (source, counts)},
        code_sha256=sha(Path(__file__)), figure_sha256=sha(output),
        scope='Saved matching group scores without a new scan; truth used for post-scan association only. '
              'Counts use unchanged bright-member identities. Connecting lines organize three fixed skies, not a continuous condition relation.'))
    print(output)


if __name__ == '__main__':
    run()
