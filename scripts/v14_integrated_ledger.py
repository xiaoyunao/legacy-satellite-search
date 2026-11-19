"""Reconcile qualified historical discovery records without borrowing alternate-sample C fits."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v14_catalog import chord,number,reconcile,source_order


def run():
    root=Path('results/v14/production_integration');out=root/'reconciled';out.mkdir(parents=True,exist_ok=True)
    registration=root/'manifest.json';saved=json.loads(registration.read_text())
    for path,checksum in saved['source_sha256'].items():
        if sha(Path(path))!=checksum:raise ValueError('Registry source snapshot changed: '+path)
    catroot=Path('results/v14/catalogue');catalog=json.loads((catroot/'manifest.json').read_text())
    qualified=read_csv(root/'eligible_record_inventory.csv')
    modes=read_csv(catroot/'candidate_modes.csv');by_detection=defaultdict(list)
    for row in modes:by_detection[row['detection_id']].append(row)
    contexts={r['candidate_id']:r for r in read_csv(catroot/'candidate_catalogue.csv')}
    detected=[];records=[]
    for record in qualified:
        path=record['input'];key=f"{Path(path).parent}:{record['group_id']}"
        if catalog['inputs'].get(path)!=record['source_sha256']:
            raise ValueError('Catalogue and registry source clocks differ: '+path)
        eligible=[r for r in by_detection[key] if r['source_kind']=='blind_peak'
                  and r['input']==path and r['channel']=='A_base' and r['policy']=='A_base'
                  and number(r['budget'])==.3 and r['role']=='pilot_eval'
                  and 16.5<=number(r['dm'])<=20.75]
        if len(eligible)!=int(record['hypothesis_rows']):raise ValueError('Eligible modes do not match registry: '+key)
        anchor=max(eligible,key=lambda r:number(r['score']))
        fits=[r for r in by_detection[key] if r['source_kind']=='C_followup']
        good=[r for r in fits if r['fit_status']=='complete' and number(r['c_ts']) is not None]
        best=max(good,key=lambda r:float(r['c_ts']),default={})
        context=contexts[anchor['candidate_id']]
        record=dict(record,detection_id=key,cohort=anchor['cohort'] or str(Path(path).parent),
            successful_same_record_C=len(good)>0,available_C_modes=len(fits),complete_C_modes=len(good),
            C_best_TS=best.get('c_ts'),C_best_after_top3=best.get('c_without_top3'),
            C_status='available_modes_complete_required_seed_audit_pending' if fits and len(good)==len(fits)
                     else 'partial_modes' if good else 'no_bound_complete_mode',
            context_from_catalogue=context['grade'],known_system=context['known_system_match'],
            extended_galaxy_context=context['extended_galaxy_ellipse_3x'])
        records.append(record)
        detected.append(dict(detection_id=key,input=path,group_id=record['group_id'],
            ra_deg=float(record['ra_deg']),dec_deg=float(record['dec_deg']),rh_arcmin=float(record['rh_arcmin']),
            score=float(record['score']),modes=sorted({float(r['dm']) for r in eligible})))
    groups,edges=reconcile(detected)
    by_cohort=defaultdict(list)
    for r in records:by_cohort[r['cohort']].append(r)
    for cohort,rows in by_cohort.items():
        for rank,r in enumerate(sorted(rows,key=lambda r:(-float(r['score']),r['detection_id'])),1):
            r['within_cohort_rank']=rank;r['within_cohort_records']=len(rows)
    associations=[];mapping={}
    for indices in groups:
        source=min((detected[j] for j in indices),key=source_order)['detection_id']
        cid='PROD-'+hashlib.sha256(source.encode()).hexdigest()[:12]
        members=[records[j] for j in indices];anchor=members[0]
        associations.append(dict(provisional_position_id=cid,ra_deg=anchor['ra_deg'],dec_deg=anchor['dec_deg'],
            source_records=len(members),cohorts='|'.join(sorted({m['cohort'] for m in members})),
            retained_dm='|'.join(map(str,sorted({dm for j in indices for dm in detected[j]['modes']}))),
            same_record_C_records=sum(m['successful_same_record_C'] for m in members),
            known_contexts='|'.join(sorted({m['known_system'] for m in members if m['known_system']})),
            human_grade=None,evidence_level='L0_or_known_context',final_frozen=False))
        for j in indices:
            records[j]['provisional_position_id']=cid;mapping[records[j]['detection_id']]=cid
    links=[dict(left_detection=detected[r['i']]['detection_id'],right_detection=detected[r['j']]['detection_id'],
        arcmin=r['arcmin'],closest_dm=r['closest_dm'],scale_ratio=r['scale_ratio'],
        jointly_compatible=r['jointly_compatible'],same_provisional_position=mapping[detected[r['i']]['detection_id']]==mapping[detected[r['j']]['detection_id']]) for r in edges]
    # Frozen identities remain certainty-inclusion cases even if later table versions relabel a group.
    cases=read_csv(Path('results/v14/shortlist/cases.csv'))
    if len(cases)!=75 or len({r['case_id'] for r in cases})!=75:raise ValueError('Frozen first-batch identities changed')
    sky=unit([float(r['ra_deg']) for r in records],[float(r['dec_deg']) for r in records]);tree=cKDTree(sky)
    by_key={r['detection_id']:r for r in records};crosswalk=[]
    for case in cases:
        p=unit([float(case['ra_deg'])],[float(case['dec_deg'])])[0]
        near=tree.query_ball_point(p,chord(5));exact=by_key.get(case['detection_id'])
        separation=(120*np.rad2deg(np.arcsin(np.linalg.norm(p-sky[records.index(exact)])/2))) if exact else None
        verified=exact is not None and separation<1e-4
        crosswalk.append(dict(case_id=case['case_id'],queue=case['queue'],frozen_detection_id=case['detection_id'],
            current_same_identity=verified,identity_offset_arcmin=separation,
            provisional_position_id=exact['provisional_position_id'] if verified else None,
            nearby_provisional_positions='|'.join(sorted({records[j]['provisional_position_id'] for j in near})),
            certainty_include=True,human_grade=None))
    write_csv(out/'qualified_discovery_records.csv',records)
    write_csv(out/'provisional_positions.csv',associations)
    write_csv(out/'potential_associations.csv',links)
    write_csv(out/'frozen75_crosswalk.csv',crosswalk)
    write_csv(out/'regional_funnel.csv',[dict(cohort=k,qualified_records=len(v),
        provisional_positions=len({r['provisional_position_id'] for r in v}),
        records_with_successful_bound_C=sum(r['successful_same_record_C'] for r in v),
        all_required_C_complete=None,effective_union_deg2=None,human_adjudicated=None) for k,v in sorted(by_cohort.items())])
    sources=[registration,root/'eligible_record_inventory.csv',catroot/'manifest.json',catroot/'candidate_modes.csv',
        catroot/'candidate_catalogue.csv',Path('results/v14/shortlist/cases.csv')]
    write_json(out/'manifest.json',dict(inputs={str(p):sha(p) for p in sources},code_sha256=sha(Path(__file__)),
        qualified_records=len(records),provisional_positions=len(associations),
        records_with_successful_bound_C=sum(r['successful_same_record_C'] for r in records),
        frozen75_verified_current_identities=sum(r['current_same_identity'] for r in crosswalk),
        C_states=dict(Counter(r['C_status'] for r in records)),final_production_frozen=False,
        scope='Qualified discovery records only, reconciled with the existing complete-link sky/DM/scale rule. Nearby incompatible hypotheses remain linked in the 5-arcmin table; these are provisional positions, not final human-review units or physical discoveries. C rows inherit the catalogue source/seed binding; a completed available row is not certification that every required seed was run. Historical raster-area union, terminal search completion, seed completeness, source-level image QA and final review-unit freeze remain gates. Frozen 75 identities are retained with empty user grades; never put this identity crosswalk in an anonymous archive.'))
    print(dict(records=len(records),positions=len(associations),frozen75=sum(r['current_same_identity'] for r in crosswalk)))


if __name__=='__main__':run()
