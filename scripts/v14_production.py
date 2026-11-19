"""Audit the completed R14 baseline main-branch sample without historical mixing."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import math
import re

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def eligibility(row):
    if row.get('source_kind') != 'blind_peak':
        return 'followup_not_discovery'
    if not re.fullmatch(r'results/v14/discovery/[^/]+/main/sky_group_candidates.csv', row['input']):
        return 'historical_or_other_branch'
    if row.get('role') != 'pilot_eval':
        return 'development_or_unknown_role'
    if row.get('channel') != 'A_base' or row.get('policy') != 'A_base':
        return 'alternate_search_policy'
    if finite(row.get('budget')) != .3:
        return 'alternate_review_budget'
    if row.get('branch') != 'main' or finite(row.get('dm')) is None or not 16.5 <= float(row['dm']) <= 20.75:
        return 'outside_frozen_main_grid'
    return 'eligible'


def select(modes):
    selected = [r for r in modes if eligibility(r) == 'eligible']
    ids = {r['detection_id'] for r in selected}
    # A C fit from a development or alternate-budget record cannot certify this sample.
    reviewed = {r['detection_id'] for r in modes if r['source_kind'] == 'C_followup'
                and r['detection_id'] in ids and r.get('fit_status') == 'complete'
                and finite(r.get('c_ts')) is not None}
    return selected, reviewed


def run(root=Path('results/v14')):
    out = root/'production'; out.mkdir(exist_ok=True)
    catalogue = root/'catalogue'
    modes = read_csv(catalogue/'candidate_modes.csv')
    source_manifest=json.loads((catalogue/'manifest.json').read_text())
    selected, reviewed = select(modes)
    associations = {r['candidate_id']: r for r in read_csv(catalogue/'candidate_catalogue.csv')}
    by_detection = defaultdict(list)
    for r in selected:
        by_detection[r['detection_id']].append(r)
    records = []
    for key, rows in by_detection.items():
        best = max(rows, key=lambda r: finite(r.get('score')) or -math.inf)
        records.append(dict(candidate_id=best['candidate_id'], detection_id=key, cohort=best['cohort'],
                            field=best['field'], ra_deg=best['ra_deg'], dec_deg=best['dec_deg'],
                            score=best['score'], highest_dm=best['dm'],
                            retained_dm='|'.join(map(str, sorted({float(r['dm']) for r in rows}))),
                            successful_C_on_eligible_record=key in reviewed,
                            association_context=associations[best['candidate_id']]['grade'],
                            visual_status='not_adjudicated_by_this_audit', input=best['input']))
    funnel, inputs = [], {}
    status = root/'discovery/status.csv'
    for state in read_csv(status):
        cohort = state['cohort']; path = root/f'discovery/{cohort}/fields.csv'
        if not path.is_file():
            raise ValueError(f'Missing summarized field ledger: {path}')
        fields = {r['field']: r for r in read_csv(path) if r['status'] == 'complete' and r['role'] == 'pilot_eval'}
        members = [r for r in records if r['cohort'] == cohort]
        if any(r['field'] not in fields for r in members):
            raise ValueError('Eligible candidate has no matching completed evaluation field')
        area = sum(float(r['searched_deg2']) for r in fields.values())
        ids = {r['candidate_id'] for r in members}
        c_ids = {r['candidate_id'] for r in members if r['successful_C_on_eligible_record']}
        calibrated = finite(state.get('primary_cut')) is not None
        if calibrated and len(members)!=int(state['primary_eval']):
            raise ValueError(f'Production record count disagrees with regional snapshot: {cohort}')
        funnel.append(dict(cohort=cohort, calibrated=calibrated, completed_evaluation_fields=len(fields),
            evaluation_owned_deg2=area, frozen_cut=state.get('primary_cut'),
            raw_peaks_all_distances=sum(int(r['raw_peaks']) for r in fields.values()),
            deduplicated_peaks_all_distances=sum(int(r['dedup_peaks']) for r in fields.values()),
            main_baseline_primary_records=len(members) if calibrated else None,
            provisional_sky_associations=len(ids) if calibrated else None,
            review_records_per_deg2=len(members)/area if calibrated and area else None,
            known_system_context=sum(associations[i]['grade']=='known_system_response' for i in ids) if calibrated else None,
            known_complex_context=sum(associations[i]['grade']=='known_complex_background' for i in ids) if calibrated else None,
            successful_C_records=sum(r['successful_C_on_eligible_record'] for r in members) if calibrated else None,
            associations_with_successful_C=len(c_ids) if calibrated else None, visual_adjudicated=None, followup_approved=None))
        inputs[str(path)] = sha(path)
    exclusions = Counter(eligibility(r) for r in modes if r['source_kind']=='blind_peak')
    write_csv(out/'baseline_records.csv', records)
    write_csv(out/'candidate_funnel.csv', funnel)
    write_csv(out/'mode_eligibility_counts.csv', [dict(reason=k, modes=v) for k,v in sorted(exclusions.items())])
    for p in (catalogue/'manifest.json', catalogue/'candidate_modes.csv', catalogue/'candidate_catalogue.csv', status):
        inputs[str(p)] = sha(p)
    write_json(out/'manifest.json', dict(inputs=inputs, source_snapshot_job=source_manifest['job'],
        code_sha256=sha(Path(__file__)), discovery_records=len(records),
        provisional_sky_associations=len({r['candidate_id'] for r in records}),
        successful_C_records=len(reviewed), main_dm=[16.5,20.75],
        scope='Completed R14 primary-budget baseline main-branch evaluation records only. Historical records remain in the inventory but are not included in this incremental sample. Area uses the same regional-summary clock as the candidate inputs. Raw/deduplicated peak totals include all distances; they are not main-only funnel stages. Associations remain provisional and can share cross-version context. Blank review stages and uncalibrated counts are unknown, not zero. No population completeness or physical confirmation is inferred.'))
    print(dict(records=len(records), provisional_associations=len({r['candidate_id'] for r in records}),
               successful_C_records=len(reviewed)), flush=True)


if __name__ == '__main__':
    run()
