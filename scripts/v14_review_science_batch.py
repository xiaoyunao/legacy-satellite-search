"""Bind six-panel derivatives to the frozen anonymous and saved-context sources."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

from PIL import Image

from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_review_science import data_for_field, render, saved_members

PRIVATE = Path('results/v14/human_review/final_private')
ASSEMBLY = PRIVATE / 'final_assembly'
INPUT_PLAN = ASSEMBLY / 'anonymous_plan.json'
INPUT_KEY = ASSEMBLY / 'held_context_key.json'
RENDERER = Path('scripts/v14_review_science.py')


def read(path):
    return json.loads(path.read_text())


def source_tasks():
    old75 = Path('results/v14/human_review/membership_integrity.csv')
    if sha(old75) != read(old75.with_suffix('.json'))['csv_sha256']:
        raise ValueError('Original 75-case membership proof changed')
    saved75 = {r['membership_sha256']: r['frozen_path'] for r in read_csv(old75)}
    data = Path(os.environ['LS_SAT_DATA'])
    base = data / 'runs/v14/human_review/final_private/density_v2/registration.json'
    earlier = read(base)
    freeze = read(ASSEMBLY / 'registration.json')
    if sha(INPUT_PLAN) != freeze['assembly_sha256'] or sha(INPUT_KEY) != freeze['held_key_sha256']:
        raise ValueError('Original anonymous plan or identity crosswalk changed')
    if sha(INPUT_PLAN) != earlier['original_plan_sha256']:
        raise ValueError('Previous source grouping belongs to another draw')
    packs = []
    for pack in earlier['packs']:
        fields = []
        for manifest_name, views in pack:
            manifest = Path(manifest_name)
            scan_hash = sha(manifest)
            tasks = []
            for task in views:
                context = Path(task['context_manifest'])
                if sha(context) != task['context_manifest_sha256']:
                    raise ValueError('Original mode context changed')
                saved = read(context)
                proof = read(Path(task['saved_preparation']))
                status, = [m for m in proof['mode_status'] if m['context_manifest'] == str(context)]
                if scan_hash != proof.get('scan_manifest_sha256', proof.get('source_manifest_sha256')):
                    raise ValueError('Saved mode belongs to another scan')
                expected = saved['membership_sha256']
                mode = saved['mode']
                relative = status.get('membership_data_path') or saved75.get(expected)
                if relative is None:
                    relative = mode.get('membership_data_path') or str(
                        Path(saved['raw_template_peaks_path']).parent /
                        f"membership-main-A-{int(float(mode['rank']))}.npz")
                member_path = data / relative
                if sha(member_path) != expected:
                    raise ValueError('Saved membership bytes differ from accepted context')
                tasks.append(dict(task, membership=str(member_path), membership_sha256=expected))
            fields.append(dict(manifest=str(manifest), scan_sha256=scan_hash, views=tasks))
        packs.append(fields)
    expected_views = sum(len(u['alternatives']) for u in read(INPUT_KEY)['units'])
    observed = {(t['unit'], t['view']) for pack in packs for f in pack for t in f['views']}
    expected = {(i, a['retained_view']) for i, u in enumerate(read(INPUT_KEY)['units'])
                for a in u['alternatives']}
    if len(observed) != expected_views or observed != expected:
        raise ValueError('Prepared views differ from the frozen draw')
    return dict(packs=packs, parent_sha256=sha(base), original_plan_sha256=sha(INPUT_PLAN),
                original_key_sha256=sha(INPUT_KEY), renderer_sha256=sha(RENDERER),
                views=expected_views, driver_sha256=sha(Path(__file__)))


def name(task):
    return f"unit_{task['unit']:04d}_view_{task['view']:03d}"


def render_field(job):
    spec, output = job
    manifest = Path(spec['manifest'])
    if sha(manifest) != spec['scan_sha256']:
        raise ValueError('Registered original scan changed')
    scan = read(manifest)
    field, area, sample, galaxies, ids, locus = data_for_field(scan)
    for task in spec['views']:
        dest = output / name(task)
        dest.mkdir(exist_ok=True)
        receipt = dest / 'receipt.json'
        context = Path(task['context_manifest'])
        member_path = Path(task['membership'])
        if sha(context) != task['context_manifest_sha256'] or sha(member_path) != task['membership_sha256']:
            raise ValueError('Registered context or membership changed')
        if receipt.exists():
            verify_view(task, dest)
            continue
        mode = read(context)['mode']
        members, prob, integrity = saved_members(member_path, mode, ids)
        sigma = .5 if float(mode['fit_rh_arcmin']) < 2 else 2.
        metrics = {}
        for suffix, width, indices, values, title in (
                ('anonymous', sigma, None, None, None),
                ('held_sigma0p5', .5, members, prob, 'Saved C hypothesis'),
                ('held_sigma2', 2., members, prob, 'Saved C hypothesis')):
            path = dest / (suffix + '.png')
            metrics[suffix] = render(path, field, area, sample, galaxies, locus, mode, indices,
                                     values, width, title, g_limit=scan['config']['g_max'])
            metrics[suffix].update(path=str(path), sha256=sha(path))
        write_json(receipt, dict(outputs=metrics, scan_sha256=spec['scan_sha256'],
                   context_sha256=task['context_manifest_sha256'], membership_integrity=integrity,
                   renderer_sha256=sha(RENDERER), job=os.environ['SLURM_JOB_ID']))
    return len(spec['views'])


def verify_view(task, dest):
    receipt = read(dest / 'receipt.json')
    if receipt['context_sha256'] != task['context_manifest_sha256'] or receipt['renderer_sha256'] != sha(RENDERER):
        raise ValueError('Rendered panels belong to different sources')
    if set(receipt['outputs']) != {'anonymous', 'held_sigma0p5', 'held_sigma2'}:
        raise ValueError('Incomplete six-panel evidence')
    for key, row in receipt['outputs'].items():
        png = Path(row['path'])
        if row['saved_C_plotted'] != (key != 'anonymous') or sha(png) != row['sha256']:
            raise ValueError('Panel role, pixels or membership policy differs')
        with Image.open(png) as im:
            im.verify()
    return receipt['outputs']


def assemble(registration, root):
    plan, held = read(INPUT_PLAN), read(INPUT_KEY)
    inputs = 0
    by_unit = [{} for _ in plan['units']]
    for pack in registration['packs']:
        for spec in pack:
            for task in spec['views']:
                rows = verify_view(task, root / 'rasters' / name(task))
                i = task['unit']
                alternative = held['units'][i]['alternatives'][task['view'] - 1]
                if alternative['retained_view'] != task['view'] or alternative['evidence_numbers'] != task['original_pages']:
                    raise ValueError('Frozen origin or page linkage differs')
                old_pages = list(alternative['evidence_numbers'])
                alternative['original_evidence_numbers'] = old_pages
                alternative['science_panels'] = [rows['held_sigma0p5'], rows['held_sigma2']]
                by_unit[i][old_pages[0]] = (alternative, rows['anonymous'])
                inputs += 1
    for i, unit in enumerate(plan['units']):
        held_unit = held['units'][i]
        if held_unit['anonymous_id'] != unit['anonymous_id']:
            raise ValueError('Anonymous unit linkage differs')
        panels = []
        for pos, panel in enumerate(unit['panels'], 1):
            if pos in by_unit[i]:
                alternative, row = by_unit[i][pos]
                alternative['evidence_numbers'] = list(range(len(panels) + 1,
                    len(panels) + 2 + len(alternative['original_evidence_numbers'])))
                panels.append(dict(path=row['path'], sha256=row['sha256']))
            panels.append(panel)
        unit['panels'] = panels
    plan.update(science_panel_supplement=True, review_version='v14-final-2')
    held.update(science_panel_supplement=True, review_version='v14-final-2')
    assembly = root / 'assembly'
    assembly.mkdir(exist_ok=False)
    write_json(assembly / 'anonymous_plan.json', plan)
    write_json(assembly / 'held_context_key.json', held)
    parent = read(ASSEMBLY / 'registration.json')
    write_json(assembly / 'registration.json', dict(parent, original_assembly_sha256=parent['assembly_sha256'],
               original_held_key_sha256=parent['held_key_sha256'], assembly_sha256=sha(assembly / 'anonymous_plan.json'),
               held_key_sha256=sha(assembly / 'held_context_key.json'), added_science_views=inputs,
               panels=sum(len(u['panels']) for u in plan['units']), review_version='v14-final-2'))
    print(dict(anonymous_units=len(plan['units']), added_science_views=inputs), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'pilot', 'pack', 'assemble'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    root = args.root
    if not os.getenv('SLURM_JOB_ID') or 'final_private' not in root.parts:
        raise RuntimeError('Use allocated CPUs and private storage')
    path = root / 'registration.json'
    if args.action == 'register':
        registration = source_tasks()
        root.mkdir(exist_ok=False)
        write_json(path, registration)
        print(dict(views=registration['views'], packs=len(registration['packs'])), flush=True)
        return
    registration = read(path)
    for key, source in (('original_plan_sha256', INPUT_PLAN), ('original_key_sha256', INPUT_KEY),
                        ('renderer_sha256', RENDERER), ('driver_sha256', Path(__file__))):
        if registration[key] != sha(source):
            raise ValueError('Registered render inputs or implementation changed')
    if args.action == 'assemble':
        assemble(registration, root)
        return
    if args.action == 'pilot':
        all_fields = [f for pack in registration['packs'] for f in pack]
        pilot = [(f, v) for f in all_fields for v in f['views'] if v['view'] == 1]
        wanted = [next((f, v) for f, v in pilot if item in v['pilot_tags'])
                  for item in ('P001', 'P007', 'DELVE_4', 'DELVE_5')]
        wanted += [(f, v) for f, v in pilot if v['probability_audit']][:2]
        specs = [dict(f, views=[v]) for f, v in wanted]
        output = root / 'pilot'
    else:
        specs = registration['packs'][args.index]
        output = root / 'rasters'
    output.mkdir(exist_ok=True)
    workers = min(len(specs), int(os.environ['SLURM_CPUS_PER_TASK']))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        views = sum(pool.map(render_field, ((s, output) for s in specs)))
    print(dict(action=args.action, views=views, index=args.index), flush=True)


if __name__ == '__main__':
    main()
