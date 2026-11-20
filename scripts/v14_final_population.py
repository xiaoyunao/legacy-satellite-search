"""Freeze the closed production review frame, then draw its registered audit.

Only aggregate tables are read. No grades, fits, likelihood thresholds or aliases
are generated. Selection keys stay private until actual human responses seal.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_bounded_review_geometry import bounded_groups
from scripts.v14_catalog import chord

ROOT = Path('results/v14/production_integration')
PRIVATE = Path('results/v14/human_review/final_private/final_population')
PLAN = Path('configs/v14_review_preparation/final_population.json')


def review_region(mask, source):
    survey = {None:'unassigned',0:'outside_census',1:'DES',2:'DELVE',3:'PS1'}[mask['survey']]
    extension = any(part.endswith('_extension') for part in Path(source).parts)
    return mask['region']+':'+survey+(':'+('extension' if extension else 'primary'))


def validate_hashes(mapping):
    for name, digest in mapping.items():
        if sha(Path(name)) != digest:
            raise ValueError('Frozen input changed: '+name)


def freeze():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Run source audit in an allocated CPU job')
    if PRIVATE.exists():
        raise ValueError('Preserve the registered population; do not overwrite')
    plan = json.loads(PLAN.read_text())
    area_path = ROOT/'masks/post_outside_C_union_acceptance.json'
    area = json.loads(area_path.read_text())
    inventory = ROOT/'masks/inventory.json'
    if (area['tiles'] != 720 or sha(inventory) != area['inventory_sha256'] or
            sha(Path(area['registration'])) != area['registration_sha256'] or
            sha(Path(area['summary'])) != area['summary_sha256']):
        raise ValueError('Current source-bound area acceptance required')
    validate_hashes(json.loads(inventory.read_text())['sources'])
    terminal_path = Path('results/v14/progress_ab20261120/terminal_acceptance.json')
    terminal = json.loads(terminal_path.read_text())
    if not terminal['all_registered_fields_terminal'] or terminal['registered_fields'] != 6891:
        raise ValueError('All registered scans must be terminal')
    validate_hashes(terminal['input_sha256'])
    ledger_path = ROOT/'reconciled/manifest.json'
    ledger = json.loads(ledger_path.read_text())
    validate_hashes(ledger['inputs'])
    if ledger['frozen75_verified_current_identities'] != 75:
        raise ValueError('All original identities must be retained')
    cover_path = ROOT/'C_seed_coverage/summary.json'
    cover = json.loads(cover_path.read_text())
    validate_hashes(cover['inputs'])
    catalog_path = Path('results/v14/catalogue/manifest.json')
    validate_hashes(json.loads(catalog_path.read_text())['inputs'])
    positions_path = ROOT/'reconciled/provisional_positions.csv'
    records_path = ROOT/'reconciled/qualified_discovery_records.csv'
    old_path = ROOT/'reconciled/frozen75_crosswalk.csv'
    modes_path = Path('results/v14/catalogue/candidate_modes.csv')
    inputs = {str(p): sha(p) for p in (PLAN, area_path, inventory, terminal_path,
        ledger_path, cover_path, catalog_path, positions_path, records_path, old_path, modes_path)}
    positions = read_csv(positions_path)
    records = read_csv(records_path)
    regions = defaultdict(set)
    for mask in json.loads(inventory.read_text())['records']:
        if mask['classification'] == 'qualified_discovery':
            for source in mask['qualified_source_tables']:
                regions[source,mask['field']].add(review_region(mask,source))
    grouped = defaultdict(list)
    for record in records:
        labels = regions[record['input'],record['field']]
        if len(labels)!=1:raise ValueError('A qualified record needs one source-bound review region')
        record['review_region'] = next(iter(labels))
        grouped[record['review_region']].append(record)
    for region, members in grouped.items():
        ratios = sorted(float(r['score'])/float(r['cutoff']) for r in members)
        for record in members:
            ratio = float(record['score'])/float(record['cutoff'])
            record['review_score_quantile'] = float(np.searchsorted(ratios,ratio,side='right')/len(ratios))
    by_position = defaultdict(list)
    for record in records:
        if record['human_grade']:
            raise ValueError('Human grades must be empty')
        by_position[record['provisional_position_id']].append(record)
    compact, stable_records = set(), set()
    qualified_ids = {r['detection_id'] for r in records}
    for mode in read_csv(modes_path):
        if (mode['source_kind']=='C_followup' and mode['fit_status']=='complete' and
                mode.get('c_without_top3') and float(mode['c_without_top3']) >= plan['C_stability_ranking_proxy']):
            stable_records.add(mode['detection_id'])
        if (mode['source_kind']=='blind_peak' and mode['detection_id'] in qualified_ids and
                mode['channel']=='A_base' and mode['policy']=='A_base' and float(mode['budget'])==.3 and
                mode['role']=='pilot_eval' and 16.5<=float(mode['dm'])<=20.75):
            pc = 1000*10**((float(mode['dm'])-10)/5)*math.tan(math.radians(float(mode['rh_arcmin'])/60))
            if pc <= plan['priority_max_rh_pc']:
                compact.add(mode['detection_id'])
    keys = [p['provisional_position_id'] for p in positions]
    points = unit([float(p['ra_deg']) for p in positions], [float(p['dec_deg']) for p in positions])
    groups = bounded_groups(points, keys, plan['span_arcmin'])
    if sorted(i for group in groups for i in group) != list(range(len(positions))):
        raise ValueError('A production position was lost or duplicated')
    owner = {}; packets = []
    for indices in groups:
        ids = sorted(keys[i] for i in indices)
        packet_id = 'UNIT-'+hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16]
        members = [r for name in ids for r in by_position[name]]
        anchor = min(members, key=lambda r:(-r['review_score_quantile'], r['detection_id']))
        clean_compact = [r for r in members if r['detection_id'] in compact and
            not (r['known_system'] or r['known_environment_context'] or r['extended_galaxy_context']) and
            (not r['nearest_known_position_arcmin'] or float(r['nearest_known_position_arcmin']) > plan['known_context_arcmin'])]
        stable = any(r['detection_id'] in stable_records for r in clean_compact)
        packets.append(dict(unit_id=packet_id, position_ids='|'.join(ids), source_records=len(members),
            region=anchor['review_region'], score_quantile=anchor['review_score_quantile'],
            compact_priority_eligible=bool(clean_compact), stability_ranking_proxy=stable,
            original75_ids='', certainty_reason='', human_grade=''))
        for name in ids:
            owner[name] = packet_id
    lookup = {p['unit_id']:p for p in packets}
    for old in read_csv(old_path):
        if old['current_same_identity'] != 'True' or old['human_grade']:
            raise ValueError('Frozen original identity invariant failed')
        packet = lookup[owner[old['provisional_position_id']]]
        packet['original75_ids'] = '|'.join(filter(None, (packet['original75_ids'], old['case_id'])))
        packet['certainty_reason'] = 'original75'
    for region in sorted({p['region'] for p in packets}):
        pool = sorted((p for p in packets if p['region']==region and p['compact_priority_eligible']),
            key=lambda p:(not p['stability_ranking_proxy'], -p['score_quantile'], p['unit_id']))
        for packet in pool[:plan['priority_per_region']]:
            packet['certainty_reason'] = '|'.join(filter(None, (packet['certainty_reason'], 'regional_compact_priority')))
    strata = defaultdict(list)
    for packet in packets:
        q = packet['score_quantile']
        index = next(i for i,(lo,hi) in enumerate(zip(plan['score_quantile_edges'], plan['score_quantile_edges'][1:])) if lo < q <= hi)
        packet['stratum'] = packet['region']+':'+str(index)
        if not packet['certainty_reason']:
            strata[packet['stratum']].append(packet)
    allocation = [dict(stratum=s, N_h=len(v), n_h=min(plan['audit_per_region_bin'],len(v)),
        pi=min(plan['audit_per_region_bin'],len(v))/len(v)) for s,v in sorted(strata.items())]
    adjacency = [dict(left_unit=owner[keys[i]], right_unit=owner[keys[j]],
        left_position=keys[i],right_position=keys[j]) for i,j in sorted(cKDTree(points).query_pairs(chord(plan['span_arcmin'])))
        if owner[keys[i]] != owner[keys[j]]]
    validate_hashes(inputs)
    PRIVATE.mkdir(parents=True)
    write_csv(PRIVATE/'frame.csv', sorted(packets,key=lambda p:p['unit_id']))
    write_csv(PRIVATE/'cross_packet_adjacency.csv', adjacency,
        keys=('left_unit','right_unit','left_position','right_position'))
    write_csv(PRIVATE/'allocation.csv', allocation)
    proof = dict(job=os.environ['SLURM_JOB_ID'], inputs=inputs, code_sha256=sha(Path(__file__)),
        geometry_code_sha256=sha(Path('scripts/v14_bounded_review_geometry.py')),
        frame_sha256=sha(PRIVATE/'frame.csv'), allocation_sha256=sha(PRIVATE/'allocation.csv'),
        adjacency_sha256=sha(PRIVATE/'cross_packet_adjacency.csv'),
        production_records=len(records),production_positions=len(positions),review_units=len(packets),
        certainty_units=sum(bool(p['certainty_reason']) for p in packets),
        strata=len(allocation),audit_units=sum(a['n_h'] for a in allocation),
        original75_retained=75,controls=plan['controls'],population_frozen=True,
        sampling_performed=False,final_ready_for_human_review=False,human_grades_filled=False,
        source_scope='Closed represented working-mask production frame. Units are administrative packets, not independent systems. Original75 prior exposure retained. No physical completeness or human classification.')
    write_json(PRIVATE/'registration.json', proof)
    write_json(Path('results/v14/human_review/final_population_registration.json'),
        {k:v for k,v in proof.items() if k!='inputs'})
    print({k:proof[k] for k in ('production_records','production_positions','review_units','certainty_units','strata','audit_units')},flush=True)


def draw():
    proof = json.loads((PRIVATE/'registration.json').read_text())
    if (proof['code_sha256'] != sha(Path(__file__)) or proof['geometry_code_sha256'] !=
            sha(Path('scripts/v14_bounded_review_geometry.py'))):
        raise ValueError('Frozen population implementation changed')
    validate_hashes(proof['inputs'])
    for name,key in [('frame.csv','frame_sha256'),('allocation.csv','allocation_sha256'),('cross_packet_adjacency.csv','adjacency_sha256')]:
        if sha(PRIVATE/name)!=proof[key]:
            raise ValueError('Registered frame changed')
    if (PRIVATE/'selection.json').exists():
        raise ValueError('Preserve the original draw')
    plan = json.loads(PLAN.read_text()); rng = np.random.default_rng(plan['sampling_seed'])
    frame = read_csv(PRIVATE/'frame.csv');selected = []
    for row in frame:
        if row['certainty_reason']:
            selected.append(dict(row,inclusion_probability=1.,selection_reason=row['certainty_reason']))
    for allocation in read_csv(PRIVATE/'allocation.csv'):
        pool=sorted((r for r in frame if r['stratum']==allocation['stratum'] and not r['certainty_reason']),key=lambda r:r['unit_id'])
        if len(pool)!=int(allocation['N_h']):raise ValueError('Stratum changed')
        for index in rng.choice(len(pool),int(allocation['n_h']),replace=False):
            selected.append(dict(pool[index],inclusion_probability=float(allocation['pi']),selection_reason='SRSWOR_audit'))
    if len({r['unit_id'] for r in selected}) != len(selected):
        raise ValueError('Duplicated selected packet')
    write_csv(PRIVATE/'selected.csv',sorted(selected,key=lambda r:r['unit_id']))
    write_json(PRIVATE/'selection.json',dict(registration_sha256=sha(PRIVATE/'registration.json'),
        selected_sha256=sha(PRIVATE/'selected.csv'),seed=plan['sampling_seed'],selected_units=len(selected),
        selection_counts=dict(Counter(r['selection_reason'] for r in selected)),
        controls=plan['controls'],aliases_generated=False,grades_filled=False,
        scope='Exact registered SRSWOR, no proximity rejection or outcome choice. Weights describe human label prevalence in this L0 frame only. Identity-bearing selection stays private; controls added separately.'))
    print('FINAL_AUDIT_DRAW',len(selected),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('freeze','draw'))
    {'freeze':freeze,'draw':draw}[parser.parse_args().mode]()
