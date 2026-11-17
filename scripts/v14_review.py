"""Run compact and high-priority modes plus a deterministic lower-priority audit sample."""
import argparse
import hashlib
from math import radians, tan
from pathlib import Path
import os

from ls_satsearch.review import review_sky_groups
from ls_satsearch.run import read_csv, write_csv, write_json


def sliced(table, output, index, count, previous):
    rows = read_csv(table)
    if not rows:
        return
    targets = [r for r in rows if r['budget']=='0.3']
    representatives = [r for r in targets if r['representative']=='True']
    compact = {r['group_id'] for r in targets
               if float(r['rh_arcmin']) <= 2 or
               1000 * 10**((float(r['dm'])-10)/5) * tan(radians(float(r['rh_arcmin'])/60)) <= 15}
    shard = lambda key: int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    seen = set()
    if previous.is_file():
        seen = {r['group_id'] for r in read_csv(previous) if int(r['modes_fit']) == int(r['modes_attempted'])}
    priority = {}
    for r in representatives:
        key = r['group_id']
        if key in seen or shard(r['field']) % count != index:
            continue
        if float(r['ranking']) >= 8.5 or key in compact:
            priority[key] = 'compact_or_high_score'
        elif shard(key) % 12 == 0:
            priority[key] = 'low_score_stratified_sample'
    output.parent.mkdir(exist_ok=True, parents=True)
    write_csv(output, [dict(r, audit_priority=priority[r['group_id']])
                       for r in targets if r['group_id'] in priority], keys=('group_id','field'))
    return bool(priority)


def run(version, cohort, index, count):
    home = Path.cwd()
    if version in ('v13','v13r'):
        base = Path(f'results/v13/discovery/{version}/{cohort}/main')
    else:
        base = Path(f'results/v14/discovery/{cohort}/main')
    table = base/'sky_group_candidates.csv'
    if not table.is_file():
        return
    dest = Path(f'results/v14/candidate_review/{version}/{cohort}/{index:02d}')
    selection = dest/'review_modes.csv'
    if not sliced(table, selection, index, count, base/'group_review_summary.csv'):
        return
    config = home/f'configs/{version}/cohorts/{cohort}'
    data = Path(os.environ['LS_SAT_DATA'])
    products = data/f'runs/v14/review/{version}/{cohort}/{index:02d}'
    workspace = home/f'regional_{version}_{cohort}'
    os.environ['LS_SAT_CONFIG_DIR'] = str(config)
    os.environ['LS_SAT_RUN_VERSION'] = version
    review_sky_groups(selection,'A_base',.3,archived_run=workspace/'results',
                      archive_version=version,products=products,blind_reference=True)
    write_json(dest/'provenance.json',dict(job=os.getenv('SLURM_JOB_ID'), input=str(table), count=count,index=index,
                                          visual_review_pending=True, blinded_cross_id=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('version')
    p.add_argument('cohort')
    p.add_argument('index', type=int)
    p.add_argument('count', type=int)
    run(**vars(p.parse_args()))
