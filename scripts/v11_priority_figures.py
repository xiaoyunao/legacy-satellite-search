"""Render a bounded, reproducible priority sample from a frozen cohort."""
import argparse
from pathlib import Path

import yaml

from ls_satsearch.paper_diagnostic import render_case
from ls_satsearch.run import read_csv


def run(cohort, limit):
    candidates = Path('results/v11')/cohort/'main/sky_group_candidates.csv'
    rows = [r for r in read_csv(candidates) if r['representative']=='True'
            and r['role']=='pilot_eval' and float(r['budget'])==.3]
    rows.sort(key=lambda r:(-float(r['ranking']),r['group_id']))
    output = Path('results/v11/priority')/cohort
    output.mkdir(exist_ok=True,parents=True)
    cases = []
    for row in rows[:limit]:
        field = row['field']
        case = dict(id=row['group_id'], label=row['group_id']+' · L0',
                    manifest=f'regional_{cohort}/results/summary/{field}-base/manifest.json',
                    ra_deg=float(row['ra_deg']),dec_deg=float(row['dec_deg']),
                    dm=float(row['dm']),rh=float(row['rh_arcmin']),panels=[dict(width=1.5,sigma=1.62)])
        cases.append(case)
    (output/'cases.yaml').write_text(yaml.safe_dump(dict(targets=cases),sort_keys=False))
    for case in cases:
        render_case(case,output)


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cohort',choices=('north','south_ps1','south_delve','south_des'))
    p.add_argument('--limit',type=int,default=2)
    args=p.parse_args()
    if args.limit<1:
        p.error('limit must be positive')
    run(args.cohort,args.limit)
