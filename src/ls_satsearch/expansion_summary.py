"""Aggregate the fixed-cut discovery batches, keeping deep controls identifiable."""

import argparse
from collections import Counter
from pathlib import Path

from .run import read_csv,write_csv


def combine(root,overlap,out,require=3):
    audit={r['field']:r for r in read_csv(overlap)}
    records,all_groups,seen=[],[],set()
    for folder in sorted(root.glob('batch*')):
        results=folder/'results/holdout'
        if not results.exists():
            results=folder/'holdout'
        counts=results/'holdout_field_summary.csv'
        review=results/'expansion_group_diagnostics.csv'
        if not counts.exists() or not review.exists():
            continue
        raw=read_csv(counts)
        groups=read_csv(review)
        if sum(int(r['kept_sky_groups']) for r in raw if float(r['budget'])==.3)!=len(groups):
            raise ValueError(f'Review count does not match the primary cut in {folder.name}')
        seen.add(folder.name)
        all_groups.extend(dict(r,batch=folder.name) for r in groups)
        for r in raw:
            name=r['field']
            g=[v for v in groups if v['field']==name]
            if float(r['budget'])==.3:
                r.update(known_catalog_nearby_groups=sum(x['known_catalog_nearby']=='True' for x in g),
                         mask_nearby_groups=sum(x['near_mask_hole_2arcmin']=='True' for x in g),
                         key_image_pending_groups=sum(x['review_status']=='key_images_pending' for x in g))
            overlap_fields={k:v for k,v in audit[name].items() if k!='field'}
            records.append(dict(r,batch=folder.name,**overlap_fields))
    if len(seen)!=require:
        raise ValueError(f'Expected {require} complete batches, got {sorted(seen)}')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'field_summary.csv',records)
    write_csv(out/'group_diagnostics.csv',all_groups)
    report=[]
    for phase in ('discovery','deep_control'):
        for budget in (.1,.3):
            subset=[r for r in records if r['phase']==phase and float(r['budget'])==budget]
            if not subset:
                continue
            area=sum(float(r['area_deg2']) for r in subset)
            number=sum(int(r['kept_sky_groups']) for r in subset)
            report.append(dict(phase=phase,budget=budget,fields=len(subset),area_deg2=area,groups=number,
                               observed_groups_per_deg2=number/area,complete_batches=len(seen)))
    write_csv(out/'discovery_summary.csv',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require',type=int,default=3)
    args=parser.parse_args()
    for row in combine(args.batches,args.audit,args.output,args.require): print(row)
