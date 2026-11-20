"""Backfill source-bound historical compact/high-score C, with original selection.

This is follow-up of already qualified discoveries, not new detection or final
human-sample selection. Registration reads aggregate tables and scan manifests;
run each registered field on Slurm. Accepted fields are never repeated.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv,sha,write_csv,write_json

BASE=Path('configs/v14_historical_C')
NAMESPACE='v14_historical_priority_20261120'


def source_settings(path):
    parts=Path(path).parts
    if parts[:3]==('results','v7','rollout'):
        return 'v7',Path('configs/v7'),Path(*parts[:4])/'results'
    if parts[:2]==('results','v11'):
        return 'v11',Path('configs/v11/cohorts')/parts[2],Path(f'regional_{parts[2]}/results')
    if parts[:3]==('results','v12','discovery') and parts[3] in ('v12','v12g'):
        version,cohort=parts[3:5]
        return version,Path('configs')/version/'cohorts'/cohort,Path(f'regional_{version}_{cohort}/results')
    raise ValueError('Historical archive needs explicit source mapping: '+path)


def register():
    if (BASE/'registration.json').exists():raise ValueError('Preserve frozen registration')
    inventory=Path('results/v14/production_integration/checkpoints/C_refresh_20261120/unattempted_priority_audit.csv')
    chosen=[r for r in read_csv(inventory) if r['existing_compact_priority']=='True' or r['existing_high_score_priority']=='True']
    if len(chosen)!=269:raise ValueError('Current historical priority population changed')
    by_source=defaultdict(list)
    for r in chosen:by_source[r['input']].append(r)
    tasks=[];sources={str(inventory):sha(inventory)}
    for source_index,(source,records) in enumerate(sorted(by_source.items())):
        version,config,archive=source_settings(source)
        if version=='v14':raise ValueError('R14 priority coverage must already be complete')
        cfg=yaml.safe_load((config/'search.yaml').read_text())
        sources[source]=sha(Path(source));sources[str(config/'search.yaml')]=sha(config/'search.yaml')
        grouped=defaultdict(list)
        for r in records:grouped[r['field']].append(r['group_id'])
        original=defaultdict(list)
        for r in read_csv(Path(source)):original[r['group_id']].append(r)
        for field,groups in sorted(grouped.items()):
            manifest=archive/'summary'/f'{field}-base/manifest.json'
            saved=json.loads(manifest.read_text())
            if saved['status']!='complete' or saved['config']!=cfg:
                raise ValueError('Original completed selection/configuration differs: '+str(manifest))
            model=Path(os.environ['LS_SAT_DATA'])/'resources'/cfg['isochrone']
            if sha(model)!=saved['model_sha256']:raise ValueError('Original stellar template changed')
            sources[str(manifest)]=sha(manifest)
            modes=[r for g in groups for r in original[g]]
            if any(r['policy']!='A_base' or float(r['budget'])!=.3 for r in modes):
                raise ValueError('Group includes another discovery policy')
            tasks.append(dict(task=len(tasks),source_key=f'historical_{source_index:02d}',input=source,
                input_sha256=sources[source],version=version,config=str(config),
                config_sha256=sha(config/'search.yaml'),archive=str(archive),field=field,
                model=cfg['isochrone'],model_sha256=saved['model_sha256'],
                scan_manifest=str(manifest),scan_manifest_sha256=sources[str(manifest)],
                group_ids='|'.join(sorted(groups)),groups=len(groups),modes=len(modes)))
    BASE.mkdir(parents=True,exist_ok=True);write_csv(BASE/'tasks.csv',tasks)
    write_json(BASE/'registration.json',dict(tasks_sha256=sha(BASE/'tasks.csv'),inputs=sources,
        groups=len(chosen),fields=len(tasks),retained_source_modes=sum(r['modes'] for r in tasks),
        existing_rule='Any retained mode rh<=2arcmin or physical rh<=15pc; or representative ranking>=8.5. Same historical qualified record, no fit borrowed from another source.',
        numerical_C_only=True,final_human_sample_selection=False,
        scope='Original configurations verified equal to original complete scan manifests. Preserve all selected group modes, including any source hypotheses outside the formal production DM interval as separately attributable follow-up context. No new detection, threshold or population claim.'))
    print(dict(fields=len(tasks),groups=len(chosen),modes=sum(r['modes'] for r in tasks)),flush=True)


def run(task):
    from ls_satsearch.review import review_sky_groups
    from scripts.v14_C_shard_accept import run as accept
    registration=json.loads((BASE/'registration.json').read_text())
    if sha(BASE/'tasks.csv')!=registration['tasks_sha256']:raise ValueError('Registered tasks changed')
    record=read_csv(BASE/'tasks.csv')[task]
    if int(record['task'])!=task:raise ValueError('Task order changed')
    source=Path(record['input']);config=Path(record['config'])
    for p,h in [(source,record['input_sha256']),(config/'search.yaml',record['config_sha256']),
                (Path(os.environ['LS_SAT_DATA'])/'resources'/record['model'],record['model_sha256']),
                (Path(record['scan_manifest']),record['scan_manifest_sha256'])]:
        if sha(p)!=h:raise ValueError('Registered original input changed: '+str(p))
    dest=Path('results/v14/candidate_review')/NAMESPACE/record['source_key']/f'{task:04d}'
    if (dest/'acceptance.json').exists():
        accept(dest);print('Verified existing accepted task',task,flush=True);return
    dest.mkdir(parents=True,exist_ok=True)
    groups=set(record['group_ids'].split('|'))
    selected=[r for r in read_csv(source) if r['group_id'] in groups]
    selection=dest/'review_modes.csv';write_csv(selection,selected)
    os.environ['LS_SAT_CONFIG_DIR']=str(config);os.environ['LS_SAT_RUN_VERSION']=record['version']
    products=Path(os.environ['LS_SAT_DATA'])/'runs/v14/review'/NAMESPACE/record['source_key']/f'{task:04d}'
    implementation=sha(Path('src/ls_satsearch/review.py'))
    review_sky_groups(selection,'A_base',.3,archived_run=Path(record['archive']),
        archive_version=record['version'],products=products,blind_reference=True,render_diagnostics=False)
    write_json(dest/'provenance.json',dict(job=os.getenv('SLURM_JOB_ID'),input=str(source),
        input_sha256=sha(source),selection_sha256=sha(selection),registered_task=task,
        registration_sha256=sha(BASE/'registration.json'),search_config_path=str(config/'search.yaml'),
        search_config_sha256=sha(config/'search.yaml'),review_implementation_sha256=implementation,
        render_diagnostics=False,diagnostic_policy='pending_final_selected_evidence',
        original_scan_manifest_sha256=record['scan_manifest_sha256'],visual_review_pending=True))
    accept(dest)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--register',action='store_true');g.add_argument('--task',type=int)
    a=p.parse_args();register() if a.register else run(a.task)
