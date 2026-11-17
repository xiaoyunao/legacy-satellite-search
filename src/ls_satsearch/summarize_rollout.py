"""Collect completed frozen fields and prioritize full-mode follow-up for visual review."""

import argparse
from collections import Counter
import os
from pathlib import Path

import yaml

from .run import read_csv, write_csv, write_json


def combine(allow_incomplete=False):
    paths=[('first',Path('results/registration/fields.yaml'),[Path('first_batch')])]
    for name in ('rollout','gaps'):
        directory=Path(f'wide_{name}')
        paths.append((name,directory/'results/registration/fields.yaml',sorted(directory.glob('batch*'))))
    output=Path('results/rollout_index')
    output.mkdir(parents=True,exist_ok=True)
    expected={}
    fields,candidates=[],[]
    completed=set()
    for phase,registry,batches in paths:
        spec=yaml.safe_load(registry.read_text())['fields']
        known={r['id']:r for r in spec}
        expected.update({r['id']:phase for r in spec})
        for folder in batches:
            holdout=folder/'results/holdout'
            tab=holdout/'holdout_field_summary.csv'
            diagnostic=holdout/'expansion_group_diagnostics.csv'
            if not tab.exists() or not diagnostic.exists():
                continue
            rows=read_csv(tab)
            groups=read_csv(diagnostic)
            ids={r['field'] for r in rows}
            if not ids<=set(known) or ids&completed:
                raise ValueError(f'Unexpected or duplicate fields from {folder}')
            target=sum(int(r['kept_sky_groups']) for r in rows if float(r['budget'])==.3)
            if len(groups)!=target:
                raise ValueError(f'Incomplete C-review table in {folder}')
            completed.update(ids)
            for r in rows:
                fields.append(dict(r,wave=phase,batch=folder.name,
                            historical_satellite_search_mask=known[r['field']]['prior_search_mask']))
            fits=read_csv(holdout/'group_review_modes.csv')
            modes={(r['candidate_group_id'],r['rank']):r for r in fits}
            for r in groups:
                fit=modes.get((r['group_id'],r['best_peak_rank']),{})
                low_context=r['known_catalog_nearby']!='True' and r['review_status']!='key_images_pending'
                severity = float(r['best_ts_without_top3'] or 0)
                candidates.append(dict(r,wave=phase,batch=folder.name,fit_ra_deg=fit.get('fit_ra_deg'),
                   fit_dec_deg=fit.get('fit_dec_deg'),manual_priority=int(low_context and severity>=2.),
                   diagnostic_directory=str(folder/'results/figures'/f"{r['field']}-base")))
    missing=sorted(set(expected)-completed)
    report=[]
    for phase in ('first','rollout','gaps','all'):
        for budget in (.1,.3):
            selected=[r for r in fields if float(r['budget'])==budget and (r['wave']==phase or phase=='all')]
            area=sum(float(r['area_deg2']) for r in selected)
            n=sum(int(r['kept_sky_groups']) for r in selected)
            if area:
                report.append(dict(wave=phase,budget=budget,completed_fields=len(selected),
                             effective_area_deg2=area,held_groups=n,groups_per_deg2=n/area))
    if fields:
        write_csv(output/'field_summary.csv',fields)
    if candidates:
        candidates.sort(key=lambda r:(-r['manual_priority'],-float(r['best_ts_without_top3'] or 0),
                      -float(r['best_ts'] or 0),r['group_id']))
        write_csv(output/'candidate_index.csv',candidates)
    if report:
        write_csv(output/'review_load.csv',report)
    write_json(output/'status.json',dict(job=os.environ.get('SLURM_JOB_ID'),registered=len(expected),
               completed=len(completed),missing=missing,unfinished_by_wave=Counter(expected[f] for f in missing),
               visual_review='pending prioritized manual triage'))
    if missing and not allow_incomplete:
        raise ValueError(f'{len(missing)} registered fields still lack a complete scan and review')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete',action='store_true')
    combine(parser.parse_args().allow_incomplete)
