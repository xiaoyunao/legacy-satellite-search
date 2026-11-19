"""Inventory actual completed discovery masks against saved production field ledgers."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

from ls_satsearch.run import read_csv,sha,write_csv,write_json

OUT=Path('results/v14/production_integration/masks')


def workspace(table):
    parts=Path(table).parts
    if parts[0] in ('wide_rollout','wide_gaps'):return Path(*parts[:2])
    version=parts[1]
    if version=='v4':return Path('../holdout-v4')
    if version in ('v5','v6'):
        return Path('../'+('discovery-v5' if version=='v5' else 'verification-v6'))/'batches'/parts[3]
    if version=='v7':return Path('first_batch') if parts[2]=='first_batch' else Path('wide_rollout')/parts[3]
    if version=='v11':return Path('regional_'+parts[2])
    if version in ('v12','v13'):return Path('regional_'+parts[3]+'_'+parts[4])
    if version=='v14':return Path('regional_v14_'+parts[3])
    raise ValueError('Unmapped discovery workspace: '+table)


def roster(table):
    policy=table.with_name('sky_group_policy.json')
    saved=json.loads(policy.read_text()) if policy.is_file() else {}
    cuts=[float(r['cutoff']) for r in saved.get('thresholds',[]) if r['policy']=='A_base'
          and float(r['budget'])==.3 and r.get('cutoff') is not None]
    blocks=table.with_name('sky_group_blocks.csv')
    rows=[r for r in read_csv(blocks) if r['policy']=='A_base' and float(r['budget'])==.3
          and r['role']=='pilot_eval'] if blocks.is_file() else []
    fields={r['field']:r for r in rows}
    metric=table.parent.parent/('fields.csv' if 'v14' in table.parts else 'field_metrics.csv')
    details={r['field']:r for r in read_csv(metric)} if metric.is_file() else {}
    return dict(table=str(table),policy=saved,cutoff=cuts[0] if len(cuts)==1 else None,
        fields=fields,details=details,source_sha256={str(p):sha(p) for p in (table,policy,blocks,metric) if p.is_file()})


def run():
    data=Path(os.environ['LS_SAT_DATA']);OUT.mkdir(parents=True,exist_ok=True)
    old=OUT/'inventory.json'
    if old.is_file():
        archive=OUT/'snapshots'/sha(old);archive.mkdir(parents=True,exist_ok=True)
        for name in ('inventory.json','inventory.csv','counts.json'):
            source=OUT/name
            if source.is_file() and not (archive/name).exists():shutil.copy2(source,archive/name)
    registration=Path('results/v14/production_integration/source_inventory.csv')
    sources=[r for r in read_csv(registration) if r['classification']=='frozen_discovery' and r['state']=='inventoried']
    proof=defaultdict(list)
    for source in sources:proof[workspace(source['input']).resolve()].append(roster(Path(source['input'])))
    frozen=data/'runs/v14/coverage_history.json';history=json.loads(frozen.read_text())
    paths={(Path.cwd().parent/r['manifest']).resolve() for r in history['rasters']}
    roots=set(proof)
    roots.update(p.resolve() for p in Path('.').glob('regional_v14_*') if p.is_dir())
    for root in roots:paths.update(p.resolve() for p in (root/'results/summary').glob('*-base/manifest.json'))
    records=[];noncomplete=Counter();source_hashes={str(registration):sha(registration),str(frozen):sha(frozen)}
    for items in proof.values():
        for item in items:source_hashes.update(item['source_sha256'])
    for path in sorted(paths):
        m=json.loads(path.read_text())
        if m.get('status')!='complete' or m.get('depth')!='base':
            noncomplete[m.get('status','unknown')]+=1;continue
        inputs=m['inputs'];field=m['field'];cfg=m['config'];root=path.parents[3]
        role=field.get('analysis_role',field.get('role'));name=field['id']
        state='complete_not_in_qualified_source_roster';accepted=[];failures=[]
        for item in proof.get(root,[]):
            if item['cutoff'] is None:failures.append('no_valid_frozen_cut');continue
            if name not in item['fields']:failures.append('not_in_source_evaluation_field_ledger');continue
            detail=item['details'].get(name,{})
            if detail.get('manifest_sha256') and detail['manifest_sha256']!=sha(path):
                failures.append('candidate_and_mask_snapshot_differ');continue
            if not math.isclose(float(item['fields'][name]['area_deg2']),m['area_deg2'],rel_tol=1e-10,abs_tol=1e-9):
                failures.append('source_field_area_differs');continue
            expected={**item['policy'].get('recipe',{}),**item['policy'].get('limits',{}).get('base',{})}
            mismatch=[k for k,v in expected.items() if cfg.get(k)!=v]
            if mismatch:failures.append('source_recipe_differs:'+','.join(mismatch));continue
            accepted.append(item['table']);source_hashes.update(item['source_sha256'])
        if field.get('truth') or 'discovery-v5/weak' in str(root) or role in ('recovery','deep_control','known_control','benchmark'):
            state='known_recovery_control'
        elif accepted and role=='pilot_eval':state='qualified_discovery'
        elif role=='pilot_dev':state='development_calibration'
        elif root.name in ('group-v3','branch-v2'):state='development_regression'
        key={k:inputs[k] for k in ('geometry','mask','subdivision','census','root','region','regional_primary') if k in inputs}
        cache=name+'-'+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]
        raster=m.get('owned_coverage_path',f'cache/{cache}/coverage.npy')
        if not (data/raster).is_file():state='missing_actual_mask'
        records.append(dict(field=name,manifest=os.path.relpath(path,Path.cwd()),manifest_sha256=sha(path),
            workspace=os.path.relpath(root,Path.cwd()),region=cfg.get('region','south'),survey=inputs.get('census'),
            role=role,classification=state,geometry=inputs['geometry'],subdivision=cfg['coverage_subdivision'],
            known_recovery_truth=field.get('truth'),
            raster=raster,apply_ownership=None if 'owned_coverage_path' in m else field.get('ownership'),
            source_effective_deg2=m['area_deg2'],qualified_source_tables=accepted,qualification_diagnostics=sorted(set(failures))))
    write_json(OUT/'inventory.json',dict(utc=datetime.now(timezone.utc).isoformat(),records=records,
        sources=source_hashes,code_sha256=sha(Path(__file__)),frozen_history_id=history['inventory_id'],
        noncomplete_manifest_states=dict(noncomplete),final_frozen=False,
        scope='Actual completed WCS-derived mask paths, evaluated against original frozen A-base primary policies and field ledgers including zero-peak fields. No stars or peak density define area. Sources/masks on different clocks remain unqualified; no total union area inferred here. Known controls, development, uncalibrated and later-completed masks remain separately inventoried.'))
    write_csv(OUT/'inventory.csv',[{k:r[k] for k in ('field','manifest','manifest_sha256','workspace','region','role','classification','raster','source_effective_deg2')} for r in records])
    write_json(OUT/'counts.json',dict(completed_mask_records=len(records),classes=dict(Counter(r['classification'] for r in records)),
        gross_record_areas_not_union={k:sum(r['source_effective_deg2'] for r in records if r['classification']==k) for k in sorted({r['classification'] for r in records})}))
    print(Counter(r['classification'] for r in records),flush=True)


if __name__=='__main__':run()
