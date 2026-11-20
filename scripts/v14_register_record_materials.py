"""Bind renderer inputs to exact existing discovery/C records; never select a final sample."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from ls_satsearch.run import read_csv,write_csv,write_json,sha
from scripts.v14_catalog import bound_fit_seed

BASE=Path('results/v14/production_integration')
OUT=Path('results/v14/human_review/final_private/record_preparation')


def run(detections=None,output=OUT,selected_records=None,supplement=None):
    records=read_csv(BASE/'reconciled/qualified_discovery_records.csv')
    modes=defaultdict(list)
    for row in read_csv(Path('results/v14/catalogue/candidate_modes.csv')):modes[row['detection_id']].append(row)
    if selected_records is not None:
        if detections:raise ValueError('Choose one explicit selection source')
        detections=[r['detection_id'] for r in read_csv(selected_records)]
    if supplement is not None:
        accepted=json.loads((supplement/'acceptance.json').read_text())
        if not accepted['exact_source_acceptance_passed'] or not accepted['all_new_C_complete']:
            raise ValueError('Selected C addendum must be accepted before rendering')
        for name,digest in accepted['inputs'].items():
            if sha(Path(name))!=digest:raise ValueError('Selected C proof changed')
        for task in read_csv(supplement/'tasks.csv'):
            folder=supplement/f"{int(task['task']):04d}"
            proof=json.loads((folder/'provenance.json').read_text())
            for line,row in enumerate(read_csv(folder/'group_review_modes.csv'),1):
                detection=f"{Path(proof['input']).parent}:{row['candidate_group_id']}"
                modes[detection].append(dict(source_kind='C_followup',fit_status=row['fit_status'],
                    input=str(folder/'group_review_modes.csv'),record_id=f'{folder}:{line}'))
    masks=defaultdict(list)
    for row in json.loads((BASE/'masks/inventory.json').read_text())['records']:
        if row['classification']=='qualified_discovery':
            for source in row['qualified_source_tables']:masks[source,row['field']].append(row)
    if detections:
        selected=[r for r in records if r['detection_id'] in set(detections)]
        if {r['detection_id'] for r in selected}!=set(detections):raise ValueError('Require exact qualified records')
    else:
        old={r['provisional_position_id'] for r in read_csv(BASE/'reconciled/frozen75_crosswalk.csv')}
        coverage={(r['input'],r['group_id']):r['C_coverage_state'] for r in read_csv(BASE/'C_seed_coverage/records.csv')}
        selected=[]
        # Readiness only: two detector/passband/source-ledger paths not in old75.
        # Existing SouthPS1 main records are already covered by the old75.
        for cohort in ('north','south_delve'):
            pool=[]
            for row in records:
                if (row['input']!=f'results/v14/discovery/{cohort}/main/sky_group_candidates.csv' or
                        row['provisional_position_id'] in old or coverage[row['input'],row['group_id']]!='all_complete'):
                    continue
                if row['known_system'] or row['known_environment_context'] or row['extended_galaxy_context']:continue
                if row['nearest_known_position_arcmin'] and float(row['nearest_known_position_arcmin'])<=30:continue
                seeds=[m for m in modes[row['detection_id']] if m['source_kind']=='blind_peak' and m['policy']=='A_base' and float(m['budget'])==.3]
                if not seeds or len(seeds)>4:continue
                if not any(1000*10**((float(m['dm'])-10)/5)*math.tan(math.radians(float(m['rh_arcmin'])/60))<=30 for m in seeds):continue
                pool.append(row)
            if not pool:raise ValueError('No bounded source-readiness case: '+cohort)
            selected.append(min(pool,key=lambda r:(not(r['C_best_after_top3'] and float(r['C_best_after_top3'])>=1),int(r['within_cohort_rank']),r['detection_id'])))
    output.mkdir(parents=True,exist_ok=False)
    inputs={str(p):sha(p) for p in map(Path,('scripts/v14_prepare_record.py','scripts/v14_phase1_panels.py',
        'scripts/v14_phase1_extent.py','scripts/v14_saved_context.py','src/ls_satsearch/review.py','src/ls_satsearch/plots.py'))}
    if selected_records is not None:inputs[str(selected_records)]=sha(selected_records)
    if supplement is not None:inputs[str(supplement/'acceptance.json')]=sha(supplement/'acceptance.json')
    fields=[];cache={}
    for index,row in enumerate(selected):
        source=Path(row['input']);inputs[str(source)]=sha(source)
        seeds=[r for r in read_csv(source) if r['group_id']==row['group_id'] and r['policy']=='A_base' and float(r['budget'])==.3]
        fitted=[]
        for seed in seeds:
            matches=[]
            for mode in modes[row['detection_id']]:
                if mode['source_kind']!='C_followup' or mode['fit_status']!='complete':continue
                path=Path(mode['input']);inputs[str(path)]=sha(path)
                if path not in cache:cache[path]=read_csv(path)
                line=int(mode['record_id'].rsplit(':',1)[1]);raw=cache[path][line-1]
                if bound_fit_seed(raw,[seed]):matches.append((str(path),line,raw))
            if not matches:raise ValueError('Missing same-record C seed; backfill before rendering')
            name,line,raw=min(matches,key=lambda r:(r[0],r[1]))
            fitted.append(dict(raw,C_origin_file=name,C_origin_line=line,C_origin_sha256=inputs[name]))
        table=output/f'record_{index}_C.csv';write_csv(table,fitted);inputs[str(table)]=sha(table)
        original=masks[row['input'],row['field']]
        if len(original)!=1:raise ValueError('Require a unique original qualified scan manifest')
        mask=original[0];inputs[mask['manifest']]=mask['manifest_sha256']
        parts=source.parts
        version='v7' if parts[0] in ('wide_rollout','wide_gaps') else parts[3] if parts[1] in ('v12','v13') else parts[1]
        fields.append(dict(record_key='REC-'+hashlib.sha256((row['detection_id']+sha(table)).encode()).hexdigest()[:16],
            source_detection_id=row['detection_id'],field=row['field'],group_ids=[row['group_id']],
            scan_manifest=mask['manifest'],seeds=str(source),fits=str(table),run_version=version,
            raw_template_peaks=f"runs/{version}/{row['field']}-base/all_template_peaks.csv"))
    write_json(output/'plan.json',dict(input_sha256=inputs,fields=fields,scope='Exact-source material registration only, no final population/draw, anonymous permutation or user grade. Default two bounded readiness cases exercise new North/South DECam sources; existing SouthPS1 main is already represented by original75. Reuse after final selection requires matching its own original source/config/member proof. Identity-bearing inputs stay private.'))
    print(dict(preparation_records=len(fields),retained_modes=[len(read_csv(Path(r['fits']))) for r in fields],final_sample_or_alias_draw=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--detections',nargs='+')
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--selected-records',type=Path)
    parser.add_argument('--supplement',type=Path)
    args=parser.parse_args();run(**vars(args))
