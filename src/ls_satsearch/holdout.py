"""Run or summarize the frozen A-baseline independent search."""

import argparse
import json
from pathlib import Path

import yaml

from . import run
from .data import load_bricks
from .group_budget import evaluate
from .search import load_isochrone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field', help='Frozen evaluation field ID or combine')
    requested = parser.parse_args().field
    policy = run.config_path('production.json')
    frozen = json.loads(policy.read_text())
    fields_path = run.config_path('fields.yaml')
    if run.sha(fields_path) != frozen['field_file_sha256']:
        raise ValueError('Field definition differs from the registered holdout')
    fields = {s['id']:s for s in yaml.safe_load(fields_path.read_text())['fields']
              if s['role']=='pilot_eval'}
    root,data,cfg = run.settings()
    if cfg != dict(frozen['recipe'],**frozen['limits']['base'],methods=['A']):
        raise ValueError('Scan settings differ from the frozen A-baseline policy')
    if requested == 'combine':
        summary = Path('results/summary')
        manifests = [json.loads(p.read_text()) for p in summary.glob('*/manifest.json')]
        actual = {r['field']['id'] for r in manifests if r['status']=='complete'
                  and r['depth']=='base' and r['field'].get('role')=='pilot_eval'}
        if actual != fields.keys() or len(manifests)!=len(actual):
            raise ValueError(f'Holdout expects exactly the frozen fields: {sorted(actual)}')
        output = Path('results/holdout')
        evaluate(summary,output,apply=policy)
        rows = run.read_csv(output/'sky_group_blocks.csv')
        by_id = {m['field']['id']:m for m in manifests}
        for r in rows:
            m = by_id[r['field']]
            g = m['observing_conditions_source_sample']['G']
            r.update(g_depth_p50=(g['depth5_dered'] or [None]*3)[1],
                     g_seeing_p50=(g['seeing'] or [None]*3)[1],
                     ebv_p50=(m['observing_conditions_source_sample']['ebv'] or [None]*3)[1],
                     selected_psf_per_deg2=m['cutflow']['inner_psf']/float(r['area_deg2']))
        run.write_csv(output/'holdout_field_summary.csv',[
            dict(r, groups_per_deg2=int(r['kept_sky_groups'])/float(r['area_deg2']),
                 layer=fields[r['field']]['layer']) for r in rows])
        return
    spec = fields[requested]
    run.execute(spec,root,data,cfg,load_bricks(root),
                load_isochrone(data/'resources'/cfg['isochrone']),'base','')


if __name__=='__main__':
    main()
