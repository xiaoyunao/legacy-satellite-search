"""Bind complete saved evidence to final anonymous units; identities stay private.

This constructs an assembly plan, not a released or human-graded package.
The anonymous permutation is generated only once, independently of the public
sampling seed. All source alternatives and original exposed cases are retained.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import secrets

from PIL import Image

from ls_satsearch.run import read_csv, sha, write_json

ROOT=Path('results/v14/human_review/final_private')
FRAME=ROOT/'final_population'
OUT=ROOT/'final_assembly'


def evidence(path,inputs):
    proof=json.loads(path.read_text());inputs[str(path)]=sha(path)
    for name,digest in proof['outputs'].items():
        if sha(Path(name))!=digest:raise ValueError('Accepted evidence changed')
    if len(proof['mode_status'])!=proof['modes']:
        raise ValueError('Saved alternative count differs')
    modes=[]
    for saved in proof['mode_status']:
        context_path=Path(saved['context_manifest']);context=json.loads(context_path.read_text())
        if (not context['membership_integrity']['verified'] or not context['image_centre_complete'] or
                context['image_missed_member_stamps'] or context['image_pending']):
            raise ValueError('Saved native/membership evidence incomplete')
        for key in ('phase1_status','extent_status'):
            if saved[key]['probabilities_or_scores_rendered']:
                raise ValueError('Phase-one information policy failed')
        panels=[]
        for key in ('phase1_path','extent_path'):
            p=Path(saved[key])
            if str(p) not in proof['outputs'] or sha(p)!=proof['outputs'][str(p)]:
                raise ValueError('Anonymous panel not bound to accepted proof')
            with Image.open(p) as image:image.verify()
            panels.append(dict(path=str(p),sha256=sha(p)))
        mode=context['mode']
        # Duplicate presentations are collapsed only when identical saved stars,
        # probabilities, fitted geometry and panel bytes agree. Every origin stays linked.
        signature=(context['membership_sha256'],*(mode[k] for k in ('fit_ra_deg','fit_dec_deg','fit_dm','fit_rh_arcmin')),
                   *(p['sha256'] for p in panels))
        modes.append(dict(signature=signature,panels=panels,context_manifest=str(context_path),
            context_manifest_sha256=sha(context_path),saved_preparation=str(path)))
    return modes


def build(material_plan):
    if OUT.exists():raise ValueError('Preserve the existing private permutation/assembly plan')
    registration=json.loads((FRAME/'registration.json').read_text())
    selection=json.loads((FRAME/'selection.json').read_text())
    if (not registration['population_frozen'] or selection['registration_sha256']!=sha(FRAME/'registration.json')
            or selection['selected_sha256']!=sha(FRAME/'selected.csv')):
        raise ValueError('Frozen final population and original draw required')
    for name,digest in registration['inputs'].items():
        if sha(Path(name))!=digest:raise ValueError('Frozen final population input changed')
    inputs={str(p):sha(p) for p in (FRAME/'registration.json',FRAME/'selection.json',FRAME/'selected.csv',material_plan)}
    plan=json.loads(material_plan.read_text())
    for name,digest in plan['input_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Registered material input changed')
    records=read_csv(Path('results/v14/production_integration/reconciled/qualified_discovery_records.csv'))
    by_position=defaultdict(list)
    for row in records:by_position[row['provisional_position_id']].append(row['detection_id'])
    prepared={}
    for field in plan['fields']:
        path=ROOT/'prepared_records'/field['record_key']/'accepted.json'
        proof=json.loads(path.read_text())
        if (proof['source_detection_id']!=field['source_detection_id'] or
                proof['scan_manifest_sha256']!=sha(Path(field['scan_manifest'])) or
                proof['source_input_sha256'][proof['source_spec']['fits']]!=sha(Path(field['fits']))):
            raise ValueError('Preparation does not bind this exact selected record')
        prepared[field['source_detection_id']]=evidence(path,inputs)
    units=[];old_seen=set();selected=read_csv(FRAME/'selected.csv')
    for unit in selected:
        origins=[];modes=[]
        for position in unit['position_ids'].split('|'):
            for detection in by_position[position]:
                if detection not in prepared:raise ValueError('Selected same-record C/evidence missing')
                modes.extend(prepared[detection]);origins.append(detection)
        old_ids=list(filter(None,unit['original75_ids'].split('|')))
        for case in old_ids:
            modes.extend(evidence(ROOT/'prepared75'/case/'accepted.json',inputs));old_seen.add(case)
        units.append(dict(unit_id=unit['unit_id'],production_record_ids=origins,old_ids=old_ids,
            selection=dict(unit),modes=modes,control=None,prior_exposure=bool(old_ids)))
    if len(old_seen)!=75:raise ValueError('All original75 must remain in final packets')
    controls=json.loads(Path('results/v14/human_review/weak_controls_preparation_acceptance.json').read_text())['controls']
    for name,proof in sorted(controls.items()):
        path=ROOT/'saved_controls'/name/proof['job']/'acceptance.json'
        if sha(path)!=proof['proof_sha256']:raise ValueError('Frozen weak-control evidence changed')
        units.append(dict(unit_id='CONTROL-'+name,production_record_ids=[],old_ids=[],selection=None,
            modes=evidence(path,inputs),control=name,prior_exposure=True))
    # A private OS-random shuffle, unrelated to publicly reproducible audit sampling.
    secrets.SystemRandom().shuffle(units)
    assembly=[];held=[]
    for i,unit in enumerate(units,1):
        alias=f'A{i:04d}';alternatives={}
        for mode in unit['modes']:
            key=tuple(mode['signature'])
            alternatives.setdefault(key,[]).append(mode)
        panels=[];sources=[]
        for j,key in enumerate(sorted(alternatives),1):
            origins=alternatives[key];mode=origins[0]
            panels.extend(dict(panel,alternative_label=f'alternative {j:02d}') for panel in mode['panels'])
            sources.append(dict(alternative_label=f'alternative {j:02d}',origins=origins))
        if not panels:raise ValueError('No observed evidence for a selected unit')
        assembly.append(dict(anonymous_id=alias,panels=panels))
        held.append(dict(anonymous_id=alias,**{k:v for k,v in unit.items() if k!='modes'},alternatives=sources))
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Evidence changed during plan assembly')
    OUT.mkdir(parents=True)
    write_json(OUT/'anonymous_plan.json',dict(pilot=False,final_population_frozen=True,units=assembly))
    write_json(OUT/'held_context_key.json',dict(units=held,publicly_reconstructible_permutation=False,
        release_only_after_actual_responses_sealed=True))
    proof=dict(inputs=inputs,assembly_sha256=sha(OUT/'anonymous_plan.json'),
        held_key_sha256=sha(OUT/'held_context_key.json'),code_sha256=sha(Path(__file__)),
        production_review_units=len(selected),weak_controls=len(controls),original75_retained=len(old_seen),
        anonymous_units=len(units),panels=sum(len(u['panels']) for u in assembly),
        human_grades_filled=False,final_ready_for_human_review=False,
        scope='Private evidence-bound assembly/permutation only. Original alternatives/source origins retained; exact duplicate pixels/geometry/member packets may share pages. Full-page, anonymity/metadata/ZIP and final release QA remain separate. Identity-bearing context withheld until actual human responses seal.')
    write_json(OUT/'registration.json',proof)
    print({k:proof[k] for k in ('production_review_units','weak_controls','original75_retained','anonymous_units','panels')},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--material-plan',type=Path,required=True)
    build(parser.parse_args().material_plan)
