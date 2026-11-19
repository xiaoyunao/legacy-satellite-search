"""Verify a completed new R14 C shard against its exact source and saved membership."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_catalog import bound_fit_seed, number, seed_signature


def run(directory):
    provenance=directory/'provenance.json';proof=json.loads(provenance.read_text())
    source=Path(proof['input']);selection=directory/'review_modes.csv'
    modes=directory/'group_review_modes.csv';summary=directory/'group_review_summary.csv'
    config=Path('configs/v14/cohorts')/directory.parent.name/'search.yaml'
    inputs={str(p):sha(p) for p in (provenance,source,selection,modes,summary,config)}
    if proof['input_sha256']!=sha(source) or proof['selection_sha256']!=sha(selection):
        raise ValueError('Source or selected seeds changed')
    if proof.get('search_config_sha256')!=sha(config):raise ValueError('C configuration differs')
    if proof.get('review_implementation_sha256')!=sha(Path('src/ls_satsearch/review.py')):
        raise ValueError('Review implementation is not the current verified version')
    original=defaultdict(list);selected=defaultdict(list)
    for r in read_csv(source):original[r['group_id']].append(r)
    for r in read_csv(selection):selected[r['group_id']].append(r)
    for key,rows in selected.items():
        if {seed_signature(r) for r in rows}!={seed_signature(r) for r in original[key]}:
            raise ValueError('Selected group lacks a complete same-source seed set')
    fitted=read_csv(modes);totals=read_csv(summary)
    expected=Counter((r['group_id'],number(r['peak_rank'])) for rows in selected.values() for r in rows)
    actual=Counter((r['candidate_group_id'],number(r['rank'])) for r in fitted)
    if expected!=actual:raise ValueError('Missing or duplicated fitted seed')
    if {r['group_id'] for r in totals}!=set(selected):raise ValueError('Group-summary coverage differs')
    data=Path(os.environ['LS_SAT_DATA']);artifacts={};states=Counter()
    for row in fitted:
        group=row['candidate_group_id'];states[row['fit_status']]+=1
        if not bound_fit_seed(row,original[group]):raise ValueError('Fit belongs to another discovery seed')
        if row['fit_status']=='complete':
            p=data/row['membership_data_path']
            if sha(p)!=row['membership_sha256']:raise ValueError('Saved membership changed')
            artifacts[str(p)]=row['membership_sha256']
            if not proof['render_diagnostics'] and (row['image_pending']!='True' or row['diagnostics_deferred']!='True'):
                raise ValueError('Deferred evidence was incorrectly accepted')
    for group in totals:
        rows=[r for r in fitted if r['candidate_group_id']==group['group_id']]
        if int(group['modes_attempted'])!=len(rows) or int(group['modes_fit'])!=sum(r['fit_status']=='complete' for r in rows):
            raise ValueError('Group-summary counters differ')
    if any(sha(Path(p))!=digest for p,digest in inputs.items()):raise ValueError('Input changed during audit')
    write_json(directory/'acceptance.json',dict(job=proof['job'],inputs=inputs,code_sha256=sha(Path(__file__)),
        exact_source_groups=len(selected),selected_seeds=sum(expected.values()),fit_states=dict(states),
        complete_membership_references=states['complete'],unique_membership_artifacts=len(artifacts),
        exact_source_and_seed_binding_passed=True,all_selected_C_fits_complete=states['complete']==sum(expected.values()),
        render_diagnostics=proof['render_diagnostics'],final_human_evidence_accepted=False,
        scope='Completed-shard source/seed/membership proof, not a final qualified-production roster, global C coverage, candidate quality or image QA. Unavailable fits remain terminal scientific attempts, distinct from missing computation. Deferred diagnostics still require final selected saved-membership-bound rendering and all review gates.'))
    print(dict(groups=len(selected),selected_seeds=sum(expected.values()),fit_states=dict(states),memberships=len(artifacts)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);run(**vars(p.parse_args()))
