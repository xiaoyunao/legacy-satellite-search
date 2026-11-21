"""Summarize qualified candidate positions without exposing review identities."""

import argparse
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.fields import Census
from ls_satsearch.run import read_csv, sha, write_csv, write_json

ROOT = Path('results/v14/production_integration')
LABELS = ('Unassigned or masked', 'DES Y6', 'DELVE DR3', 'PS1 DR1')
CONTEXTS = (('known_system_or_position', 'Known-system positional context', '#344b70'),
            ('known_environment_only', 'Known environment', '#b48142'),
            ('extended_galaxy_only', 'Extended galaxy context', '#5c857e'),
            ('no_catalogue_context', 'No listed context', '#abb8c3'))


def run(output):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Read the full census mask on allocated CPUs')
    p = ROOT / 'reconciled' / 'provisional_positions.csv'
    receipt = ROOT / 'reconciled' / 'manifest.json'
    source = ROOT / 'masks' / 'post_outside_C_union_acceptance.json'
    catalogue = read_csv(p)
    counted = json.loads(receipt.read_text())['provisional_positions']
    if len({r['provisional_position_id'] for r in catalogue}) != len(catalogue) or len(catalogue) != counted:
        raise ValueError('Reconciled position inventory changed')
    if any(r['human_grade'] for r in catalogue):
        raise ValueError('Use the frozen ungraded comparison snapshot')
    data = Path(os.environ['LS_SAT_DATA'])
    census = Census(data)
    ra, dec = (np.array([float(r[k]) for r in catalogue]) for k in ('ra_deg','dec_deg'))
    membership = np.array([census.accept(ra, dec, i) for i in range(len(LABELS))])
    if not np.all(membership.sum(axis=0) == 1):
        raise ValueError('Require one census label per representative sky position')
    label = np.argmax(membership, axis=0)
    area = json.loads(source.read_text())['layers']['qualified_production']
    areas = {int(r['census_label']): r['unambiguous_deg2'] for r in area['census']}
    contexts = {}
    for key, row in enumerate(catalogue):
        if row['known_contexts'] or row['known_position_contexts']:
            tag = CONTEXTS[0][0]
        elif row['known_environment_contexts']:
            tag = CONTEXTS[1][0]
        elif row['extended_galaxy_contexts']:
            tag = CONTEXTS[2][0]
        else:
            tag = CONTEXTS[3][0]
        contexts[key] = tag
    summary = []
    for i, census_name in enumerate(LABELS):
        selected = np.flatnonzero(label == i)
        total = len(selected)
        row = dict(census=census_name, provisional_positions=total, represented_unambiguous_deg2=areas[i],
                   approximate_positions_per_deg2=total / areas[i],
                   positions_with_same_record_C=sum(int(catalogue[j]['same_record_C_records']) > 0 for j in selected))
        row.update({tag: sum(contexts[j] == tag for j in selected) for tag, _, _ in CONTEXTS})
        summary.append(row)
    output.mkdir(parents=True, exist_ok=True)
    table = output / 'candidate_population_by_census.csv'
    write_csv(table, summary)
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.4), layout='constrained')
    y = np.arange(len(LABELS))
    previous = np.zeros(len(y))
    for tag, text, color in CONTEXTS:
        counts = np.array([r[tag] for r in summary])
        left.barh(y, counts, left=previous, color=color, label=text)
        previous += counts
    left.set(yticks=y, yticklabels=LABELS, xlabel='Provisional positions', title='Catalogue context')
    left.invert_yaxis()
    left.legend(loc='upper center', bbox_to_anchor=(.5, -.18), ncol=2, frameon=False, fontsize=8.5)
    density = [r['approximate_positions_per_deg2'] for r in summary]
    right.barh(y, density, color='#5068a4')
    for i, row in enumerate(summary):
        percent = 100 * row['positions_with_same_record_C'] / row['provisional_positions']
        right.text(density[i] + .012, i, f'{percent:.0f}% with C', va='center', fontsize=9)
    right.set(yticks=y, yticklabels=LABELS, xlim=(0, max(density) * 1.4),
              xlabel='Approx. positions per deg²', title='Provisional search burden')
    right.invert_yaxis()
    fig.suptitle(f'{counted:,} provisional positions in the qualified DR11 search')
    files = [table]
    for suffix in ('png', 'pdf'):
        figure = output / f'candidate_population_by_census.{suffix}'
        fig.savefig(figure, dpi=175)
        files.append(figure)
    plt.close(fig)
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'],
        inputs={str(k): sha(k) for k in (p, receipt, source, data/'resources/census.fits', data/'resources/read_config.yaml')},
        outputs={k.name: sha(k) for k in files}, code_sha256=sha(Path(__file__)),
        scope='Ungraded provisional catalogue positions only. Context labels have precedence in displayed order so each position is counted once. Density uses representative exact census labels and the published unambiguous WCS-mask areas, with a small boundary mismatch. Existing same-record C has at least one completed fit; it does not certify all modes. These are search burden and context counts, not false-positive rates, true objects, the frozen anonymous sample or human grades.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    run(p.parse_args().output)
