"""Render fixed-centre Table 8 diagnostics and one field control for scale comparison."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from ls_satsearch.paper_diagnostic import render_case
from ls_satsearch.run import read_csv


def run(output):
    rows=read_csv(Path('results/v12/table8/tan_table8_ls.csv'))
    gold={r['key']:r for r in read_csv(Path(
        'references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv'))}
    for row in rows:
        if row['depth']!='base' or row['status']!='complete':
            continue
        region,name = row['region'],row['field']
        truth=gold[row['key']]
        case=dict(id=name,label=row['name']+' · literature centre',
                  manifest=f'table8_v12_{region}/results/summary/{name}-base/manifest.json',
                  ra_deg=float(truth['ra']),dec_deg=float(truth['dec']),dm=float(row['truth_dm']),
                  rh=float(row['diagnostic_rh_arcmin']),
                  panels=[dict(width=1.5,sigma=1.62)])
        if float(row['rh_arcmin'])<2:
            case['panels'].append(dict(width=.30,sigma=.5,suffix='-compact'))
        with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
            render_case(case,output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    run(p.parse_args().output)
