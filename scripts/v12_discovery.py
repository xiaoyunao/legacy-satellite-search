"""Apply the frozen regional policies and process a bounded priority review."""

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

from ls_satsearch.paper_diagnostic import render_case
from ls_satsearch.regional_pilot import combine
from ls_satsearch.review import review_sky_groups
from ls_satsearch.run import read_csv, write_csv


def run(cohort, version, priority, output_root=Path("results/v12/discovery")):
    workspace=Path(f'regional_{version}_{cohort}')
    config=Path(f'configs/{version}/cohorts/{cohort}')
    output=output_root/version/cohort
    frozen=Path('configs/v7/production.json') if cohort=='south_ps1' else Path(
        f'results/v11/{cohort}/main/calibration/sky_group_policy.json')
    combine(workspace/'results/summary',config/'fields.yaml',output,policy=frozen)
    src=output/'main/sky_group_candidates.csv'
    candidates=[r for r in read_csv(src) if r['budget']=='0.3']
    reps=sorted([r for r in candidates if r['representative']=='True'],
                key=lambda r:(-float(r['ranking']),r['group_id']))
    keys={r['group_id'] for r in reps[:priority]} | {r['group_id'] for r in reps if float(r['ranking'])>=8.5}
    shortlist=output/'main/priority_modes.csv'
    write_csv(shortlist,[r for r in candidates if r['group_id'] in keys],keys=('group_id',))
    if not keys:
        return
    os.environ['LS_SAT_CONFIG_DIR']=str(config)
    os.environ['LS_SAT_RUN_VERSION']=version
    # Ordinary visual-review panels remain at NERSC. The paper atlas and
    # group-level statistics can be selected for synchronization.
    review_sky_groups(shortlist,'A_base',.3,archived_run=workspace/'results',
                      archive_version=version,products=workspace/'review')
    figures=output/'figures'
    figures.mkdir(exist_ok=True)
    cases=[]
    for row in reps[:min(2,priority)]:
        field=row['field']
        case=dict(id=row['group_id'],label=row['group_id']+' · L0',
                  manifest=str(workspace/'results/summary'/f'{field}-base'/'manifest.json'),
                  ra_deg=float(row['ra_deg']),dec_deg=float(row['dec_deg']),
                  dm=float(row['dm']),rh=float(row['rh_arcmin']),
                  panels=[dict(width=1.5,sigma=1.62)] +
                         ([dict(width=.30,sigma=.5,suffix='-core')] if float(row['rh_arcmin'])<=2 else []))
        cases.append(case)
        with plt.rc_context({'font.family':'serif','svg.fonttype':'none','pdf.fonttype':42}):
            render_case(case,figures)
    (figures/'cases.yaml').write_text(yaml.safe_dump(dict(targets=cases),sort_keys=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('cohort')
    p.add_argument('--version',default='v12')
    p.add_argument('--priority',type=int,default=3)
    p.add_argument('--output-root',type=Path,default=Path('results/v12/discovery'))
    run(**vars(p.parse_args()))
