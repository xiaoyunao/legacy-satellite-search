"""Join the inspected candidate groups and measure field-to-field review load."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open('w', newline='') as stream:
        table = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        table.writeheader()
        table.writerows(rows)


def summarize(root):
    output = root/'expansion'
    counts = read(output/'field_summary.csv')
    groups = read(output/'group_diagnostics.csv')
    field_registry = yaml.safe_load((root/'registration/fields.yaml').read_text())['fields']
    positions = {f['id']: (f['ra'], f['dec']) for f in field_registry}

    inspections = {}
    fits = {}
    scope = {}
    for batch in sorted({g['batch'] for g in groups}):
        holdout = root/'batches'/batch/'results/holdout'
        inspections.update({r['group_id']: r for r in read(holdout/'visual_review.csv')})
        modes = read(holdout/'group_review_modes.csv')
        fits.update({(r['candidate_group_id'], r['rank']): r for r in modes})
        scope[batch] = dict(modes=len(modes),
                            groups=sum(g['batch'] == batch for g in groups))
    if set(inspections) != {g['group_id'] for g in groups}:
        raise ValueError('Expected one visual disposition for every main-budget group')

    candidates = []
    for group in groups:
        best = fits.get((group['group_id'],group['best_peak_rank']), {})
        record = dict(group, **{k: best.get(k, '') for k in ('fit_ra_deg','fit_dec_deg')})
        record.update(inspections[group['group_id']])
        candidates.append(record)
    write(output/'pilot_candidate_summary.csv', candidates)

    rng = np.random.default_rng(481708)
    review = []
    for budget in (.1, .3):
        block = [r for r in counts if float(r['budget']) == budget]
        area = np.array([float(r['area_deg2']) for r in block])
        groups_each = np.array([int(r['kept_sky_groups']) for r in block])
        draw = rng.integers(0, len(block), size=(10000,len(block)))
        boot = groups_each[draw].sum(axis=1)/area[draw].sum(axis=1)
        review.append(dict(budget=budget, area_deg2=float(area.sum()), groups=int(groups_each.sum()),
                           observed_groups_per_deg2=float(groups_each.sum()/area.sum()),
                           block_bootstrap_95=np.quantile(boot,[.025,.975]).tolist(),
                           median_field_density=float(np.median(groups_each/area)),
                           fields_with_no_groups=int((groups_each==0).sum())))
    (output/'review_load.json').write_text(json.dumps(dict(budgets=review, batches=scope,
                    inspected=len(candidates)),indent=2)+'\n')

    main = [r for r in counts if float(r['budget']) == .3]
    fig, axes = plt.subplots(2,1,figsize=(9,6),layout='constrained')
    ra,dec = np.asarray([positions[r['field']] for r in main]).T
    groups_each = np.array([int(r['kept_sky_groups']) for r in main])
    dens = np.array([float(r['groups_per_deg2']) for r in main])
    scatter = axes[0].scatter(ra,dec,c=dens,s=55,edgecolors='black',linewidths=.4,cmap='viridis')
    axes[0].set(xlabel='RA (deg)',ylabel='Dec (deg)',title='Frozen A-baseline fields in PS1 census regions')
    fig.colorbar(scatter, ax=axes[0], label='Groups per effective deg²')
    axes[1].bar(range(len(main)),groups_each,color='#2b6487')
    axes[1].set(ylabel='Primary-cut groups',xticks=range(len(main)),
                xticklabels=[r['field'].removeprefix('verify_') for r in main],xlabel='Verification field')
    fig.savefig(output/'field_review_load.png',dpi=145)
    plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('results',type=Path,default=Path('results/v6'),nargs='?')
    summarize(p.parse_args().results)
