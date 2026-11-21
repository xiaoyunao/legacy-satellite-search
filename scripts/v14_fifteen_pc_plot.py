"""Plot the accepted common-stamp 10/15 pc CCD comparison."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root):
    table = root / 'full_pairs.csv'
    acceptance = root / 'full_acceptance.json'
    proof = json.loads(acceptance.read_text())
    if not proof['every_input_verified'] or checksum(table) != proof['table_sha256']:
        raise ValueError('Require the verified full comparison table')
    with table.open() as stream:
        rows = list(csv.DictReader(stream))
    arms = ('baseline', 'deeper')
    cases = [sorted([r for r in rows if r['arm'] == arm], key=lambda r: (r['site'],r['original_trial']))
             for arm in arms]
    if len(cases[0]) != len(cases[1]) or len(rows) != proof['measured_pairs']:
        raise ValueError('The two depth arms have different trial support')

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.1), layout='constrained')
    left, right = axes
    stages = [('Native initial', 'N_initial', cases[0]), ('Native final', 'N_final', cases[0]),
              ('PSF', 'N_psf', cases[0]), ('Baseline cuts', 'N_used', cases[0]), ('Deeper cuts', 'N_used', cases[1])]
    dx = np.linspace(-.13,.13,len(cases[0]))
    for j, (_, key, sample) in enumerate(stages):
        change = [int(r[f'delta_{key}']) for r in sample]
        left.scatter(np.repeat(j,len(sample))+dx, change, color='#285c85', linewidths=0, s=28)
        left.plot([j-.20,j+.20], [np.median(change)]*2, color='#151c22', lw=2)
    left.axhline(0, color='.6', lw=1)
    left.set_xticks(range(len(stages)), [label for label,_,_ in stages], rotation=18, ha='right')
    left.set(ylabel='Change in associated sources (15 pc − 10 pc)', title='Native detection and catalogue selection')

    endpoints = [(label, key, sample) for arm, sample in zip(arms, cases)
                 for label, key in ((f'{arm.title()}\nposition', 'spatial'),
                                    (f'{arm.title()}\ndistance', 'blind_correct'))]
    offset = .17
    for radius, shift, colour in ((10,-offset,'#a0b5c8'), (15,offset,'#285c85')):
        count = [sum(r[f'r{radius}_{key}']=='True' for r in sample) for _,key,sample in endpoints]
        bars = right.bar(np.arange(len(endpoints))+shift,count,width=.31,color=colour,label=f'{radius} pc')
        right.bar_label(bars,padding=2)
    right.set_xticks(range(len(endpoints)),[label for label,_,_ in endpoints])
    right.set(ylim=(0,len(cases[0])+1.7),ylabel='Paired background–population cases',title='Blind A recovery')
    right.legend(frameon=False, ncol=2, loc='upper right')
    fig.suptitle('100 kpc · identical rendered populations at 10 and 15 pc')
    outputs = {}
    for kind in ('png','pdf'):
        path=root/f'paired_radius_ccd.{kind}'
        fig.savefig(path,dpi=200)
        outputs[path.name]=checksum(path)
    plt.close(fig)
    (root/'paired_radius_figure_manifest.json').write_text(json.dumps(dict(
        accepted_table_sha256=checksum(table), acceptance_sha256=checksum(acceptance),
        code_sha256=checksum(Path(__file__)), outputs=outputs,
        scope='Six paired cases from two shared latent populations and three backgrounds. Marks at left denote individual pairs and stage medians. Distance means the highest blind mode is correct. Conditional common-stamp comparison without extrapolation to a true-V population.'
    ), indent=2)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    a=p.parse_args()
    run(a.root)
