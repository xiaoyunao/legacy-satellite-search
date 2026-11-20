"""Audit literature benchmarks against actual qualified masks and blind records.

Truth is used only after scanning. Centre coverage is reported as such, never
as full-object coverage, an injection selection function or forced recovery.
"""
from collections import defaultdict
import json
import math
import os
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv,sha,write_csv,write_json

ROOT=Path('results/v14/production_integration')
OUT=ROOT/'benchmark_audit'


def separation(a,d,b,e):
    a,d,b,e=np.deg2rad([a,d,b,e])
    value=np.sin((d-e)/2)**2+np.cos(d)*np.cos(e)*np.sin((a-b)/2)**2
    return float(np.rad2deg(2*np.arcsin(np.sqrt(np.clip(value,0,1))))*60)


def run():
    import shapely
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU for cached actual masks')
    receipt=ROOT/'masks/post_outside_C_registration_20261120.json'
    bound=json.loads(receipt.read_text());registration=Path(bound['registration'])
    if sha(registration)!=bound['registration_sha256']:raise ValueError('Area registration changed')
    geometry=json.loads(registration.read_text());index_path=Path(geometry['output'])/'vector_index.json'
    index=json.loads(index_path.read_text())
    if index['registration_sha256']!=sha(registration):raise ValueError('Require actual current polygon index')
    table=Path('references/benchmarks.csv');benchmarks=read_csv(table)
    catalogue=Path('results/v14/catalogue/candidate_modes.csv');records_path=ROOT/'reconciled/qualified_discovery_records.csv'
    records={r['detection_id']:r for r in read_csv(records_path)}
    inputs={str(p):sha(p) for p in (receipt,registration,index_path,table,catalogue,records_path)}
    centres=[shapely.Point(float(b['ra_deg']),math.sin(math.radians(float(b['dec_deg'])))) for b in benchmarks]
    coverage=[set() for _ in benchmarks];cache=Path(geometry['cache'])
    for record in index['records']:
        if record['classification']!='qualified_discovery':continue
        for label,bounds in enumerate(record['bounds']):
            if bounds is None:continue
            relevant=[i for i,p in enumerate(centres) if bounds[0]<=p.x<=bounds[2] and bounds[1]<=p.y<=bounds[3]]
            if not relevant:continue
            path=cache/f"{record['cache_key']}-{label}.wkb"
            if sha(path)!=record['geometry_sha256'][path.name]:raise ValueError('Qualified polygon changed')
            inputs[str(path)]=sha(path);polygon=shapely.from_wkb(path.read_bytes())
            for i in relevant:
                if polygon.covers(centres[i]):coverage[i].add(record['cache_key'])
    by_detection=defaultdict(list)
    for mode in read_csv(catalogue):
        source=records.get(mode['detection_id'])
        if (source is not None and mode['source_kind']=='blind_peak' and mode['policy']=='A_base'
                and mode['channel']=='A_base' and float(mode['budget'])==.3
                and 16.5<=float(mode['dm'])<=20.75 and float(mode['score'])>=float(source['cutoff'])):
            by_detection[mode['detection_id']].append(mode)
    summaries=[];details=[]
    for i,truth in enumerate(benchmarks):
        true_dm=5*math.log10(float(truth['D_kpc']))+10
        radius=max(2.,float(truth['theta_h_arcmin']))
        matched=[];any_mode_match=False
        for detection,modes in by_detection.items():
            passing=[m for m in modes if separation(float(truth['ra_deg']),float(truth['dec_deg']),float(m['ra_deg']),float(m['dec_deg']))<=radius]
            if not passing:continue
            source=records[detection];any_mode_match=True
            anchor_matches=separation(float(truth['ra_deg']),float(truth['dec_deg']),
                float(source['ra_deg']),float(source['dec_deg']))<=radius
            if anchor_matches:matched.append((source,passing))
            for mode in passing:
                offset=separation(float(truth['ra_deg']),float(truth['dec_deg']),float(mode['ra_deg']),float(mode['dec_deg']))
                details.append(dict(name=truth['name'],detection_id=detection,input=source['input'],field=source['field'],
                    source_sha256=source['source_sha256'],within_source_rank=source['within_cohort_rank'],
                    group_anchor_within_radius=anchor_matches,
                    offset_arcmin=offset,offset_over_theta_h=offset/float(truth['theta_h_arcmin']),
                    dm=mode['dm'],dm_error=float(mode['dm'])-true_dm,rh_arcmin=mode['rh_arcmin'],
                    score=mode['score'],cutoff=source['cutoff'],representative=mode['representative']))
        supported=16.5<=true_dm<=20.75
        state=('outside_formal_main_distance' if not supported else
               'centre_outside_qualified_masks' if not coverage[i] else
               'ordinary_spatial_match' if matched else 'no_retained_qualifying_spatial_match')
        summaries.append(dict(**truth,literature_dm=true_dm,formal_main_distance=supported,
            centre_in_qualified_mask=bool(coverage[i]),covering_qualified_mask_keys=len(coverage[i]),
            position_match_radius_arcmin=radius,matched_qualified_records=len(matched),
            ordinary_spatial_match=bool(matched),retained_dm_within_0p25=any(abs(float(m['dm'])-true_dm)<=.25 for _,ms in matched for m in ms),
            any_retained_mode_spatial_match=any_mode_match,
            retained_dm_within_0p75=any(abs(float(m['dm'])-true_dm)<=.75 for _,ms in matched for m in ms),
            highest_blind_mode_within_0p25=any(m['representative']=='True' and abs(float(m['dm'])-true_dm)<=.25 for _,ms in matched for m in ms),
            scale_below_0p5= float(truth['theta_h_arcmin'])<.5,status=state,forced_centre_fit=False,
            special_processing_audit='Not remeasured here; retain separate per-object processing audits.'))
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Actual source changed during audit')
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/'known_recovery_summary.csv',summaries)
    write_csv(OUT/'matched_modes.csv',details)
    write_json(OUT/'manifest.json',dict(job=os.environ['SLURM_JOB_ID'],inputs=inputs,
        code_sha256=sha(Path(__file__)),benchmarks=len(benchmarks),
        output_sha256={str(p):sha(p) for p in (OUT/'known_recovery_summary.csv',OUT/'matched_modes.csv')},
        scope='Post-search association of the fixed18literature benchmarks with qualified ordinary production records. Uses the existing max(2arcmin,theta_h) positional rule and separate0.25/0.75mag distance endpoints. Every matching record/mode and original source rank retained; no global cross-region rank. Qualified actual represented-mask coverage is at the literature centre only, not full system/background-ring coverage. Development, forced-centre, alternate-depth/distance and standalone recovery experiments excluded. Chance matches, special processing and scale mismatch remain caveats. No population completeness or physical classification.'))
    print(dict(benchmarks=len(benchmarks),qualified_centre_coverage=sum(bool(x) for x in coverage),matched_mode_rows=len(details)),flush=True)


if __name__=='__main__':run()
