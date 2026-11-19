"""Freeze independent production follow-up positions and review them before full-area completion."""
import argparse
from collections import defaultdict
import hashlib
import math
import os
from pathlib import Path
import shutil

import numpy as np
import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_production import eligibility, finite


def separation(a, b):
    def unit(r):
        ra, dec = np.deg2rad([float(r['ra_deg']), float(r['dec_deg'])])
        return np.array([np.cos(ra)*np.cos(dec), np.sin(ra)*np.cos(dec), np.sin(dec)])
    return float(np.rad2deg(2*np.arcsin(np.clip(np.linalg.norm(unit(a)-unit(b))/2, 0, 1)))*60)


def independent(row, selected, radius):
    return all(separation(row, old) >= radius for old in selected)


def choose_priority(pools, count, radius):
    selected = []
    pools = {k: list(v) for k,v in pools.items()}
    while len(selected) < count:
        added = False
        for cohort in sorted(pools):
            while pools[cohort]:
                row = pools[cohort].pop(0)
                if independent(row, selected, radius):
                    selected.append(row); added = True; break
            if len(selected) == count:
                break
        if not added:
            break
    return selected


def build():
    root = Path('results/v14'); out = root/'shortlist'; out.mkdir(exist_ok=True)
    config = Path('configs/v14/shortlist_plan.yaml'); plan = yaml.safe_load(config.read_text())
    records = read_csv(root/'production/baseline_records.csv')
    associations={r['candidate_id']:r for r in read_csv(root/'catalogue/candidate_catalogue.csv')}
    modes = read_csv(root/'catalogue/candidate_modes.csv')
    discovery = defaultdict(list); fits = defaultdict(list)
    for r in modes:
        if eligibility(r) == 'eligible': discovery[r['detection_id']].append(r)
        elif r['source_kind']=='C_followup' and r.get('fit_status')=='complete' and finite(r.get('c_ts')) is not None:
            fits[r['detection_id']].append(r)
    cohorts = defaultdict(list)
    for row in records: cohorts[row['cohort']].append(row)
    pools = {}; annotated = []
    for cohort, rows in sorted(cohorts.items()):
        scores = sorted(float(r['score']) for r in rows)
        available = []
        for original in rows:
            row = dict(original); key = row['detection_id']; retained = discovery[key]
            context=associations[row['candidate_id']]
            near=finite(context.get('nearest_arcmin'))
            known_position=bool(context.get('nearest_within_30arcmin')) and near is not None and near<=plan['known_position_context_arcmin']
            compact = any(1000*10**((float(m['dm'])-10)/5)*math.tan(math.radians(float(m['rh_arcmin'])/60))
                          <= plan['priority_max_rh_pc'] for m in retained)
            complete = fits[key]
            stable = any((finite(m.get('c_without_top3')) or 0) >= plan['c_stability_ranking_proxy'] for m in complete)
            best = max(complete, key=lambda m: finite(m.get('c_ts')) or -1, default={})
            quantile = float(np.searchsorted(scores, float(row['score']), side='right')/len(scores))
            row.update(score_quantile_within_cohort=quantile, rank_tier=0 if stable else 1 if not complete else 2,
                       any_stable_C_mode=stable, best_C_TS=best.get('c_ts'),
                       best_C_after_top3=best.get('c_without_top3'), compact_mode=compact,
                       source_group_id=key.rsplit(':',1)[1],
                       nearby_known_position=context.get('nearest_within_30arcmin'), nearby_known_arcmin=near,
                       known_position_context=known_position,
                       independent_imaging_status='not_queried_for_this_queue', evidence_level='L0')
            annotated.append(row)
            if compact and not known_position and row['association_context'] in ('L0','priority_L0'): available.append(row)
        pools[cohort] = sorted(available, key=lambda r:(r['rank_tier'],-r['score_quantile_within_cohort'],r['detection_id']))
    priority = choose_priority(pools, plan['priority_positions'], plan['independent_position_arcmin'])
    if len(priority)!=plan['priority_positions']: raise ValueError('Insufficient independent priority positions')
    occupied = list(priority); audit = []; edges = plan['score_quantile_edges']
    for cohort in sorted(cohorts):
        for j,(lo,hi) in enumerate(zip(edges,edges[1:])):
            pool = [r for r in annotated if r['cohort']==cohort and lo < r['score_quantile_within_cohort'] <= hi]
            pool.sort(key=lambda r:hashlib.sha256(f"{plan['seed']}:{r['detection_id']}".encode()).hexdigest())
            chosen = 0
            for r in pool:
                if independent(r, occupied, plan['independent_position_arcmin']):
                    row = dict(r, score_bin=j); audit.append(row); occupied.append(row); chosen += 1
                if chosen == plan['low_per_cohort_bin']: break
    cases = [dict(r,case_id=f'P{i:03d}',queue='priority') for i,r in enumerate(priority,1)]
    cases += [dict(r,case_id=f'B{i:03d}',queue='stratified_blind_audit') for i,r in enumerate(audit,1)]
    write_csv(out/'priority_shortlist.csv',cases[:len(priority)])
    write_csv(out/'audit_selection_key.csv',cases[len(priority):])
    write_csv(out/'cases.csv',cases)
    write_csv(out/'known_position_context.csv',[r for r in annotated if r['known_position_context']])
    write_csv(out/'blinded_audit.csv',[{k:r[k] for k in ('case_id','ra_deg','dec_deg','retained_dm')} for r in cases if r['queue']=='stratified_blind_audit'])
    selected = {r['detection_id'] for r in cases}
    sources = {}
    for cohort in sorted(cohorts):
        paths = {r['input'] for r in cases if r['cohort']==cohort}
        rows = []
        for name in sorted(paths):
            path = Path(name); sources[name] = sha(path)
            for r in read_csv(path):
                if f'{path.parent}:{r["group_id"]}' in selected and r['policy']=='A_base' and r['budget']=='0.3': rows.append(r)
        write_csv(out/f'input_modes_{cohort}.csv',rows,keys=('group_id','field'))
    packets=[out/'cases.csv',*sorted(out.glob('input_modes_*.csv'))]
    write_json(out/'manifest.json',dict(plan_sha256=sha(config), source_hashes=sources,
        packet_hashes={str(p):sha(p) for p in packets},
        production_manifest_sha256=sha(root/'production/manifest.json'),
        priority_positions=len(priority), audit_positions=len(audit),
        counts_by_cohort={c:sum(r['cohort']==c for r in cases) for c in sorted(cohorts)},
        scope=plan['scope']+' C stability is a ranking proxy only. Missing C is not zero. '
        'The 5 arcmin separation controls independent follow-up positions, without changing the discovery associations. '
        'Known positions within 30 arcmin route to context/control review irrespective of distance-mode agreement; this is not a physical membership assertion. '
        'Blind audit is registered, not graded; the identity key must not be read during grading. No candidate is promoted by selection.'))
    print(dict(priority=len(priority),blind_audit=len(audit)),flush=True)


def review_shard(index, count, case_id=None):
    from ls_satsearch.review import review_sky_groups
    import json
    home=Path.cwd(); out=home/'results/v14/shortlist'
    manifest=json.loads((out/'manifest.json').read_text())
    if sha(home/'configs/v14/shortlist_plan.yaml')!=manifest['plan_sha256']:
        raise ValueError('Shortlist plan changed after registration')
    if any(sha(Path(name))!=value for name,value in manifest['packet_hashes'].items()):
        raise ValueError('Shortlist packet changed after registration')
    data=Path(os.environ['LS_SAT_DATA']); cases=read_csv(out/'cases.csv')
    cache=out/'cache_manifest.json'
    reused=json.loads(cache.read_text()) if cache.is_file() else {}
    if reused.get('shortlist_manifest_sha256')==sha(out/'manifest.json') and case_id is None:
        cases=[r for r in cases if r['case_id'] not in reused.get('complete_cases',[])]
    if case_id is not None:
        cases=[r for r in cases if r['case_id']==case_id]
        if len(cases)!=1: raise ValueError('Unknown or duplicate shortlist case')
    for cohort in sorted({r['cohort'] for r in cases}):
        source=out/f'input_modes_{cohort}.csv'
        wanted={r['source_group_id'] for r in cases if r['cohort']==cohort}
        rows=[r for r in read_csv(source) if r['group_id'] in wanted and
              int(hashlib.sha256(r['field'].encode()).hexdigest()[:12],16)%count==index]
        if not rows: continue
        shard=f'smoke-{case_id}' if case_id else f'{index:02d}'
        dest=home/f'results/v14/candidate_review/shortlist/{cohort}/{shard}'
        dest.mkdir(parents=True,exist_ok=True); table=dest/'review_modes.csv'; write_csv(table,rows)
        products=data/f'runs/v14/review/shortlist/{cohort}/{shard}'
        os.environ['LS_SAT_CONFIG_DIR']=str(home/f'configs/v14/cohorts/{cohort}')
        os.environ['LS_SAT_RUN_VERSION']='v14'
        review_sky_groups(table,'A_base',.3,archived_run=home/f'regional_v14_{cohort}/results',
                          archive_version='v14',products=products,blind_reference=True)
        fits=read_csv(dest/'group_review_modes.csv')
        for case in (r for r in cases if r['cohort']==cohort):
            group=[r for r in fits if r['candidate_group_id']==case['source_group_id']]
            if not group: continue
            folder=out/'cases'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
            write_csv(folder/'review_modes.csv',group)
            for r in group:
                if r['fit_status']!='complete':continue
                rank=int(float(r['rank']))
                base=products/'figures'/f'{r["field"]}-base'
                for suffix in ('','-environment','-images'):
                    path=base/f'candidate-main-A-{rank}{suffix}.png'
                    if path.is_file(): shutil.copy2(path,folder/f'seed-{rank}{suffix}.png')
        write_json(dest/'provenance.json',dict(job=os.getenv('SLURM_JOB_ID'), index=index,count=count,
            input_sha256=sha(source), plan_sha256=manifest['plan_sha256'],
            actual_visual_grading=False, scope='Blind-reference multimode C and diagnostic images. No evidence promotion.'))


def reuse():
    """Materialize already completed C tables/images; never refit or read source FITS."""
    import json
    out=Path('results/v14/shortlist');data=Path(os.environ['LS_SAT_DATA'])
    all_modes=read_csv(Path('results/v14/catalogue/candidate_modes.csv'))
    available=defaultdict(list)
    for row in all_modes:
        if row['source_kind']=='C_followup' and row.get('fit_status')=='complete':
            available[row['detection_id']].append(row)
    packets={};full_tables={};complete=[];sources={}
    for case in read_csv(out/'cases.csv'):
        cohort=case['cohort']
        if cohort not in packets:packets[cohort]=read_csv(out/f'input_modes_{cohort}.csv')
        needed={int(float(r['peak_rank'])) for r in packets[cohort] if r['group_id']==case['source_group_id']}
        fitted={};images={}
        for meta in available[case['detection_id']]:
            path=Path(meta['input'])
            if 'candidate_review' not in path.parts:continue
            if path not in full_tables:full_tables[path]=read_csv(path)
            part=path.parts.index('candidate_review')
            base=data/'runs/v14/review'/Path(*path.parts[part+1:-1])/'figures'/f'{case["field"]}-base'
            for row in full_tables[path]:
                if row['candidate_group_id']!=case['source_group_id'] or row['fit_status']!='complete':continue
                rank=int(float(row['rank']))
                paths=[base/f'candidate-main-A-{rank}{suffix}.png' for suffix in ('','-environment','-images')]
                if all(p.is_file() for p in paths):
                    fitted[rank]=row;images[rank]=paths;sources[str(path)]=sha(path)
        if not needed or not needed<=set(fitted):continue
        folder=out/'cached_cases'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
        write_csv(folder/'review_modes.csv',[fitted[r] for r in sorted(needed)])
        for rank in sorted(needed):
            for path,suffix in zip(images[rank],('','-environment','-images')):
                shutil.copy2(path,folder/f'seed-{rank}{suffix}.png')
        complete.append(case['case_id'])
    write_json(out/'cache_manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),complete_cases=complete,
        shortlist_manifest_sha256=sha(out/'manifest.json'),source_hashes=sources,
        scope='Reuse of complete existing same-record C modes and their actual diagnostic PNGs; not a new measurement or independent evidence. Visual grading is separate.'))
    print('Reused complete C packets',len(complete),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('mode',choices=('build','review','reuse'))
    p.add_argument('--index',type=int,default=0);p.add_argument('--count',type=int,default=1)
    p.add_argument('--case',dest='case_id')
    a=p.parse_args()
    if a.mode=='build': build()
    elif a.mode=='review': review_shard(a.index,a.count,a.case_id)
    else: reuse()
