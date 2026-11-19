"""Compare preserved full-render partial fits with the same restarted numerical C."""
import argparse
from pathlib import Path

from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_catalog import number
import os


def run(index):
    root=Path('results/v14/candidate_review/v14/south_delve')
    current=root/f'{index:02d}';old=root/f'{index:02d}_full_render_attempt0'
    if sha(current/'review_modes.csv')!=sha(old/'review_modes.csv'):
        raise ValueError('Restarted selected hypotheses differ')
    key=lambda r:(r['field'],r['candidate_group_id'],number(r['rank']),number(r['seed_dm']),number(r['seed_rh_arcmin']))
    fits={key(r):r for r in read_csv(current/'group_review_modes.csv')}
    previous=Path(os.environ['LS_SAT_DATA'])/'runs/v14/review/v14/south_delve'/f'{index:02d}_full_render_attempt0/summary'
    paths=sorted(previous.glob('*/review.csv'));inputs={str(p):sha(p) for p in paths}
    compared=0;positive=0;columns=set()
    ignored={'g_depth_local_p10_p50_p90','g_seeing_local_p10_p50_p90','ebv_local_p10_p50_p90'}
    for path in paths:
        for row in read_csv(path):
            new=fits[key(row)]
            fields=[k for k in row if k in new and k not in ignored and not k.startswith(('image_','g_source','r_source')) and k not in ('g_centre','r_centre')]
            if any(row[k]!=new[k] for k in fields):raise ValueError('Scientific partial-fit value changed')
            compared+=1;columns.update(fields);positive+=float(row.get('ts') or 0)>0
    if not compared:raise ValueError('No preserved field-level fits to compare')
    if any(sha(Path(p))!=v for p,v in inputs.items()):raise ValueError('Preserved table changed')
    write_json(current/'preserved_partial_comparison.json',dict(inputs=inputs,current_modes_sha256=sha(current/'group_review_modes.csv'),
        original_selection_sha256=sha(old/'review_modes.csv'),restarted_selection_sha256=sha(current/'review_modes.csv'),
        code_sha256=sha(Path(__file__)),compared_partial_fits=compared,positive_TS_fits=positive,scientific_columns=sorted(columns),
        all_common_scientific_values_and_membership_hashes_identical=True,
        scope='Exact old-versus-new comparison for all available preserved completed field tables, including immutable membership hashes. No new fit or image extraction. This subset is operationally available, not a random scientific validation sample or full-workflow timing benchmark. Diagnostic availability/condition plotting metadata differ by design and remain separately pending.'))
    print(index,compared,'preserved fits identical;',positive,'positive TS')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('index',type=int,choices=(4,5));run(**vars(p.parse_args()))
