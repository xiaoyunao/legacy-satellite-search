"""Audit historical discovery qualification before final mask/sky reconciliation."""
from collections import Counter, defaultdict
import json
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_catalog import number


def eligibility(row, classification, limits):
    if classification!='frozen_discovery':return classification
    if row.get('role')!='pilot_eval':return 'development_or_unknown_role'
    if row.get('policy')!=limits['policy'] or row.get('channel')!=limits['policy']:
        return 'alternate_depth_or_method'
    if number(row.get('budget'))!=limits['budget']:return 'alternate_review_budget'
    dm=number(row.get('dm'))
    if dm is None or not limits['main_dm'][0]<=dm<=limits['main_dm'][1]:
        return 'outside_formal_main_grid'
    return 'eligible_hypothesis'


def run():
    path=Path('configs/v14/production_registry.yaml');spec=yaml.safe_load(path.read_text())
    out=Path('results/v14/production_integration');out.mkdir(parents=True,exist_ok=True)
    inventory=[];records=[];groups=[];counts=Counter();sources={str(path):sha(path)};seen=set()
    for source in spec['sources']:
        paths=sorted(Path('.').glob(source['pattern']))
        if not paths:
            inventory.append(dict(pattern=source['pattern'],input=None,classification=source['class'],state='not_available_in_this_snapshot'))
        for table in paths:
            if table in seen:raise ValueError('Overlapping production registry patterns: '+str(table))
            seen.add(table);checksum=sha(table);sources[str(table)]=checksum
            rows=read_csv(table);policy=table.with_name('sky_group_policy.json');cut=None
            if source['class']=='frozen_discovery' and policy.is_file():
                p=json.loads(policy.read_text())
                cuts=[float(x['cutoff']) for x in p['thresholds']
                      if x.get('policy')==spec['policy'] and number(x.get('budget'))==spec['budget']
                      and number(x.get('cutoff')) is not None]
                if len(cuts)==1:cut=cuts[0]
                sources[str(policy)]=sha(policy)
            by_group=defaultdict(list)
            for index,row in enumerate(rows,1):
                status=eligibility(row,source['class'],spec)
                if status=='eligible_hypothesis' and cut is None:status='missing_frozen_policy_proof'
                counts[status]+=1
                records.append(dict(input=str(table),line=index,group_id=row.get('group_id'),field=row.get('field') or row.get('field_id'),
                    classification=source['class'],eligibility=status,policy=row.get('policy'),budget=row.get('budget'),
                    channel=row.get('channel'),dm=row.get('dm'),score=row.get('score'),source_sha256=checksum))
                if status=='eligible_hypothesis':by_group[row['group_id']].append(row)
            before=len(groups)
            for group,items in by_group.items():
                best=max(items,key=lambda r:number(r.get('ranking'),r.get('score')))
                ranking=number(best.get('ranking'),best.get('score'))
                if ranking<cut:continue
                groups.append(dict(input=str(table),group_id=group,field=best['field'],source_sha256=checksum,
                    ra_deg=best['ra_deg'],dec_deg=best['dec_deg'],highest_dm=best['dm'],rh_arcmin=best['rh_arcmin'],
                    score=ranking,cutoff=cut,retained_dm='|'.join(map(str,sorted({float(r['dm']) for r in items}))),
                    hypothesis_rows=len(items),C_status='requires_same_record_reconciliation',
                    area_status='requires_completed_mask_and_overlap_reconciliation',human_grade=None))
            inventory.append(dict(pattern=source['pattern'],input=str(table),classification=source['class'],state='inventoried',
                hypothesis_rows=len(rows),eligible_groups=len(groups)-before if cut is not None else None,cutoff=cut,source_sha256=checksum,
                policy_sha256=sha(policy) if policy.is_file() else None))
    write_csv(out/'source_inventory.csv',inventory)
    write_csv(out/'hypothesis_eligibility.csv',records)
    write_csv(out/'eligible_record_inventory.csv',groups)
    write_csv(out/'eligibility_counts.csv',[dict(reason=k,hypotheses=v) for k,v in sorted(counts.items())])
    write_json(out/'manifest.json',dict(source_sha256=sources,code_sha256=sha(Path(__file__)),
        inventoried_tables=len(seen),qualified_discovery_records=len(groups),final_production_frozen=False,
        scope='Actual candidate tables classified against their saved frozen A-base primary policy and development roles. Follow-up indices never count as discovery. These are source records, not independent positions or a final production sample. No summed or inferred area, inherited C certification, human grades or new discoveries. Historical mask union, original 75 crosswalk, complete regional inputs and same-record C remain required.'))
    print(dict(tables=len(seen),qualified_source_records=len(groups),final_frozen=False))


if __name__=='__main__':run()
