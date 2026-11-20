"""Backfill only the exact qualified records selected by the frozen review draw.

Identity-bearing tasks, outputs and original configurations remain private.
The discovery frame and published C snapshot are never rewritten by this step.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json

ROOT = Path('results/v14/human_review/final_private')
FRAME = ROOT/'final_population'
OUT = ROOT/'selected_C'
PRODUCTION = Path('results/v14/production_integration')


def check(mapping):
    for name, digest in mapping.items():
        if sha(Path(name)) != digest:
            raise ValueError('Registered source changed: '+name)


def selected_records(selected, records):
    positions = {p for unit in selected for p in unit['position_ids'].split('|')}
    found = [r for r in records if r['provisional_position_id'] in positions]
    if {r['provisional_position_id'] for r in found} != positions:
        raise ValueError('Selected position lacks its qualified source records')
    return sorted(found, key=lambda r:r['detection_id'])


def register():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Register original scan/model inputs on an allocated CPU')
    if OUT.exists():
        raise ValueError('Preserve the original selected-C registration')
    frame = json.loads((FRAME/'registration.json').read_text())
    draw = json.loads((FRAME/'selection.json').read_text())
    if (not frame['population_frozen'] or draw['registration_sha256'] != sha(FRAME/'registration.json')
            or draw['selected_sha256'] != sha(FRAME/'selected.csv')):
        raise ValueError('A frozen population and its actual registered draw are required')
    check(frame['inputs'])
    paths = [FRAME/'registration.json', FRAME/'selection.json', FRAME/'selected.csv',
             PRODUCTION/'reconciled/qualified_discovery_records.csv',
             PRODUCTION/'C_seed_coverage/records.csv', PRODUCTION/'masks/inventory.json',
             Path('scripts/v14_selected_C.py'), Path('src/ls_satsearch/review.py')]
    inputs = {str(p):sha(p) for p in paths}
    records = selected_records(read_csv(FRAME/'selected.csv'), read_csv(paths[3]))
    coverage = {(r['input'],r['group_id']):r['C_coverage_state'] for r in read_csv(paths[4])}
    masks = defaultdict(list)
    for mask in json.loads(paths[5].read_text())['records']:
        if mask['classification'] == 'qualified_discovery':
            for source in mask['qualified_source_tables']:
                masks[source,mask['field']].append(mask)
    missing = defaultdict(list)
    for row in records:
        state = coverage[row['input'],row['group_id']]
        if state == 'all_complete':
            continue
        if state != 'not_attempted':
            raise ValueError('Preserve and inspect partial/unavailable C; do not silently retry')
        missing[row['input'],row['field']].append(row)
    tasks = []
    configurations = []
    data = Path(os.environ['LS_SAT_DATA'])
    for (source,field), rows in sorted(missing.items()):
        matched = masks[source,field]
        if len(matched) != 1:
            raise ValueError('Require one exact qualified scan manifest')
        mask = matched[0]; manifest = Path(mask['manifest'])
        if sha(manifest) != mask['manifest_sha256']:
            raise ValueError('Original scan manifest changed')
        saved = json.loads(manifest.read_text())
        if saved['status'] != 'complete' or saved['depth'] != 'base' or saved['field']['id'] != field:
            raise ValueError('Require the original completed baseline scan')
        model = data/'resources'/saved['config']['isochrone']
        if sha(model) != saved['model_sha256']:
            raise ValueError('Original stellar template changed')
        index = len(tasks); configuration = OUT/f'{index:04d}/config/search.yaml'
        groups = {r['group_id'] for r in rows}
        seeds = [r for r in read_csv(Path(source)) if r['group_id'] in groups]
        if ({r['group_id'] for r in seeds} != groups or
                any(r['policy'] != 'A_base' or float(r['budget']) != .3 for r in seeds)):
            raise ValueError('Require all modes of the same qualified production record')
        inputs[source] = sha(Path(source)); inputs[str(manifest)] = sha(manifest)
        inputs[str(model)] = sha(model)
        tasks.append(dict(task=index,input=source,field=field,group_ids='|'.join(sorted(groups)),
            scan_manifest=str(manifest),archive=str(manifest.parents[2]),
            config=str(configuration),groups=len(groups),seeds=len(seeds)))
        configurations.append(saved['config'])
    check(inputs)
    OUT.mkdir(parents=True)
    for task,cfg in zip(tasks,configurations):
        path=Path(task['config']);path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(cfg,sort_keys=False))
        if yaml.safe_load(path.read_text()) != cfg:
            raise ValueError('Original configuration round trip failed')
        inputs[str(path)] = sha(path)
    write_csv(OUT/'selected_records.csv',records)
    write_csv(OUT/'tasks.csv',tasks,keys=('task','input','field','group_ids','scan_manifest','archive','config','groups','seeds'))
    inputs[str(OUT/'selected_records.csv')] = sha(OUT/'selected_records.csv')
    inputs[str(OUT/'tasks.csv')] = sha(OUT/'tasks.csv')
    proof = dict(job=os.environ['SLURM_JOB_ID'],inputs=inputs,tasks=len(tasks),
        selected_records=len(records),reused_complete_records=len(records)-sum(t['groups'] for t in tasks),
        missing_records=sum(t['groups'] for t in tasks),missing_seeds=sum(t['seeds'] for t in tasks),
        discovery_frame_changed=False,identities_private=True,human_grades_filled=False)
    write_json(OUT/'registration.json',proof)
    print({k:proof[k] for k in ('tasks','selected_records','reused_complete_records','missing_records','missing_seeds')},flush=True)


def run(index):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Numerical C requires allocated CPUs')
    from ls_satsearch.review import review_sky_groups
    from scripts.v14_C_shard_accept import run as accept
    proof=json.loads((OUT/'registration.json').read_text());check(proof['inputs'])
    record=read_csv(OUT/'tasks.csv')[index]
    if int(record['task']) != index:raise ValueError('Registered task order changed')
    dest=OUT/f'{index:04d}'
    if (dest/'acceptance.json').exists():
        accept(dest);print('Verified existing selected-C task',index,flush=True);return
    if (dest/'provenance.json').exists():
        # A finished numerical call may have lacked its final validator only.
        accept(dest);print('Accepted completed selected-C task',index,flush=True);return
    config=Path(record['config']);source=Path(record['input'])
    groups=set(record['group_ids'].split('|'))
    selected=[r for r in read_csv(source) if r['group_id'] in groups]
    selection=dest/'review_modes.csv';write_csv(selection,selected)
    namespace=f'v14_final_selected_C_{index:04d}'
    os.environ['LS_SAT_CONFIG_DIR']=str(config.parent)
    os.environ['LS_SAT_RUN_VERSION']=namespace
    products=Path(os.environ['LS_SAT_DATA'])/'runs/v14/review/final_selected'/f'{index:04d}'
    review_sky_groups(selection,'A_base',.3,archived_run=Path(record['archive']),
        products=products,blind_reference=True,render_diagnostics=False)
    write_json(dest/'provenance.json',dict(job=os.environ['SLURM_JOB_ID'],input=str(source),
        input_sha256=sha(source),selection_sha256=sha(selection),registered_task=index,
        registration_sha256=sha(OUT/'registration.json'),search_config_path=str(config),
        search_config_sha256=sha(config),review_implementation_sha256=sha(Path('src/ls_satsearch/review.py')),
        render_diagnostics=False,original_scan_manifest_sha256=sha(Path(record['scan_manifest'])),
        diagnostics_pending=True,private_selected_addendum=True))
    accept(dest)


def collect():
    from scripts.v14_C_shard_accept import run as accept
    proof=json.loads((OUT/'registration.json').read_text());check(proof['inputs'])
    states=Counter();inputs={str(OUT/'registration.json'):sha(OUT/'registration.json')}
    for task in read_csv(OUT/'tasks.csv'):
        dest=OUT/f"{int(task['task']):04d}";accept(dest)
        receipt=dest/'acceptance.json';row=json.loads(receipt.read_text())
        states.update(row['fit_states']);inputs[str(receipt)]=sha(receipt)
    result=dict(inputs=inputs,tasks=proof['tasks'],new_C_states=dict(states),
        selected_records=proof['selected_records'],reused_complete_records=proof['reused_complete_records'],
        exact_source_acceptance_passed=True,all_new_C_complete=not any(k!='complete' for k in states),
        material_QA_complete=False,human_grades_filled=False,identities_private=True)
    write_json(OUT/'acceptance.json',result)
    write_json(Path('results/v14/human_review/selected_C_acceptance.json'),
        {k:v for k,v in result.items() if k!='inputs'})
    print({k:v for k,v in result.items() if k!='inputs'},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('register','run','collect'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    {'register':register,'run':lambda:run(args.index),'collect':collect}[args.mode]()
