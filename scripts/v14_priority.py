"""Export the compact L0 cases with the strongest residual C scores."""
import argparse
import os
from pathlib import Path
from shutil import copyfile

import matplotlib.pyplot as plt
import yaml

from ls_satsearch.paper_diagnostic import render_case
from ls_satsearch.run import read_csv


def run(index):
    cases = yaml.safe_load(Path('configs/v14/priority_cases.yaml').read_text())['targets']
    case = cases[index]
    output = Path('results/v14/priority_figures')
    with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
        render_case(case,output)
    root = Path('results/v14/candidate_review/v13r/south_ps1')
    reviewed = [(file.parent.name, row)
                for file in root.glob('*/group_review_modes.csv')
                for row in read_csv(file) if row['candidate_group_id']==case['id']
                and row['fit_status']=='complete']
    shard, fit = min(reviewed, key=lambda r: abs(float(r[1]['fit_ra_deg'])-case['ra_deg']) +
                                           abs(float(r[1]['fit_dec_deg'])-case['dec_deg']))
    scratch = Path(os.environ['LS_SAT_DATA'])/f'runs/v14/review/v13r/south_ps1/{shard}'
    stem = scratch/'figures'/f"{fit['field']}-base"/f"candidate-main-A-{fit['rank']}"
    for suffix in ('-images.png','-environment.png'):
        source = stem.with_name(stem.name+suffix)
        if source.is_file():
            copyfile(source,output/(case['id']+suffix))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('index',type=int)
    run(p.parse_args().index)
