"""Run compact and high-priority modes plus a deterministic lower-priority audit sample."""
import argparse
from collections import Counter
import hashlib
import json
from math import radians, tan
from pathlib import Path
import os

from ls_satsearch.review import review_sky_groups
from ls_satsearch.run import read_csv, sha, write_csv, write_json
if __package__:
    from .v14_catalog import seed_signature
else:
    from v14_catalog import seed_signature


def completed_prior_groups(table, exclude=None, root=Path('results/v14/candidate_review')):
    current={}
    for row in read_csv(table):
        current.setdefault(row['group_id'],set()).add(seed_signature(row))
    seen=set()
    for provenance in root.glob('*/*/*/provenance.json'):
        if provenance.parent==exclude:continue
        saved=json.loads(provenance.read_text())
        selection=provenance.with_name('review_modes.csv')
        summary=provenance.with_name('group_review_summary.csv')
        fitted=provenance.with_name('group_review_modes.csv')
        if (saved.get('input')!=str(table) or not selection.is_file()
                or not summary.is_file() or not fitted.is_file()):continue
        if saved.get('selection_sha256') and saved['selection_sha256']!=sha(selection):
            raise ValueError('Prior C selection changed after fitting')
        seeds={}
        for row in read_csv(selection):
            seeds.setdefault(row['group_id'],set()).add(seed_signature(row))
        fitted_counts=Counter(r['candidate_group_id'] for r in read_csv(fitted) if r['fit_status']=='complete')
        for row in read_csv(summary):
            key=row['group_id']
            if (int(row['modes_attempted'])>0 and row['modes_fit']==row['modes_attempted']
                    and fitted_counts[key]==int(row['modes_attempted'])
                    and seeds.get(key)==current.get(key)):
                seen.add(key)
    return seen


def sliced(table, output, index, count, previous, extra_seen=()):
    rows = read_csv(table)
    if not rows:
        return
    targets = [r for r in rows if r['budget']=='0.3']
    representatives = [r for r in targets if r['representative']=='True']
    compact = {r['group_id'] for r in targets
               if float(r['rh_arcmin']) <= 2 or
               1000 * 10**((float(r['dm'])-10)/5) * tan(radians(float(r['rh_arcmin'])/60)) <= 15}
    shard = lambda key: int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    seen = set(extra_seen)
    if previous.is_file():
        seen.update(r['group_id'] for r in read_csv(previous) if int(r['modes_fit']) == int(r['modes_attempted']))
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
    tag=os.getenv('LS_SAT_REVIEW_TAG','')
    if tag and not all(c.isalnum() or c in '_-' for c in tag):raise ValueError('Invalid review pass tag')
    namespace=version+'_'+tag if tag else version
    dest = Path(f'results/v14/candidate_review/{namespace}/{cohort}/{index:02d}')
    selection = dest/'review_modes.csv'
    seen=completed_prior_groups(table,exclude=dest) if tag else set()
    if not sliced(table, selection, index, count, base/'group_review_summary.csv',extra_seen=seen):
        return
    source_checksum=sha(table)
    config = home/f'configs/{version}/cohorts/{cohort}'
    data = Path(os.environ['LS_SAT_DATA'])
    products = data/f'runs/v14/review/{namespace}/{cohort}/{index:02d}'
    workspace = home/f'regional_{version}_{cohort}'
    os.environ['LS_SAT_CONFIG_DIR'] = str(config)
    os.environ['LS_SAT_RUN_VERSION'] = version
    review_sky_groups(selection,'A_base',.3,archived_run=workspace/'results',
                      archive_version=version,products=products,blind_reference=True)
    write_json(dest/'provenance.json',dict(job=os.getenv('SLURM_JOB_ID'), input=str(table),
                                          input_sha256=source_checksum,selection_sha256=sha(selection),count=count,index=index,
                                          visual_review_pending=True, blinded_cross_id=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('version')
    p.add_argument('cohort')
    p.add_argument('index', type=int)
    p.add_argument('count', type=int)
    run(**vars(p.parse_args()))
