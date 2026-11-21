"""Hold finite stellar populations fixed across a 10/15 pc real CCD replay."""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import reddening
from ls_satsearch.run import field_cache, read_csv, sha, write_csv, write_json
from ls_satsearch.search import CMD, load_isochrone
from scripts import v13_image_trials as native
from scripts.v14_production_deeper_replay import MATCHED, load_registration

VERSION = 'v14_fifteen_pc'
CONFIG = Path('configs') / VERSION
OUTPUT = Path('results/v14/fifteen_pc')
PARENT = Path('configs/v14_repeat')
BASE = Path('results/v14/repeat_full/production_replay/registration.json')
RADII = (10, 15)
LUMINOSITY_ORDINALS = (2, 5)


def read(path):
    return json.loads(path.read_text())


def register(data):
    if (OUTPUT / 'registration.json').exists():
        verify_registration()
        return
    sites = read_csv(PARENT / 'image_fields.csv')
    plan = yaml.safe_load((PARENT / 'image_trials.yaml').read_text())
    parents = [i for i, spec in enumerate(plan['conditions']) if spec == [100, 10, -3.]]
    if len(sites) != 3 or len(parents) != 8:
        raise ValueError('Original three skies and eight latent populations required')
    # Preselected luminosity ordinals avoid recovery-based choice. Rank once
    # on the shared parent IMF light, before examining any 15 pc outcomes.
    def light(parent):
        name = sites[0]['field']
        meta = read(data / 'image-v14_repeat' / name / f'trial{parent:02d}' / 'truth.json')
        return float(meta['realized_MV_proxy']), parent
    parents = [sorted(parents, key=light)[k] for k in LUMINOSITY_ORDINALS]
    splice = plan['splice_radius_arcmin']
    deep_path, deep = load_registration()
    reference = read(BASE)
    if reference['width_deg'] != deep['width_deg'] or reference['buffer_arcmin'] != deep['buffer_arcmin']:
        raise ValueError('Formal A arm geometry differs')
    for name, checksum in reference['source_sha256'].items():
        if sha(Path(name)) != checksum:
            raise ValueError('Frozen formal baseline input changed')
    inputs = [BASE, deep_path, MATCHED, PARENT / 'image_fields.csv', PARENT / 'image_trials.yaml',
              Path('scripts/v13_native.py'), Path('scripts/v13_native.sh'), Path('scripts/v13_image_trials.py')]
    tasks, retention = [], []
    for k, parent in enumerate(parents):
        stored = []
        for site in sites:
            name = site['field']
            old = data / 'image-v14_repeat' / name / f'trial{parent:02d}'
            truth, receipt = old / 'truth.npy', Path('results/v14/repeat/validation') / f'{name}-trial{parent:02d}.json'
            if sha(truth) != read(receipt)['truth_sha256']:
                raise ValueError('Accepted original truth changed')
            table, meta = np.load(truth, allow_pickle=False), read(old / 'truth.json')
            if (meta['D_kpc'], meta['rh_pc'], meta['expected_MV_proxy']) != (100, 10, -3):
                raise ValueError('Require the original 100 kpc, 10 pc parent')
            field = native.local_coordinates(site)
            center = np.array(field.xy(meta['truth_ra_deg'], meta['truth_dec_deg']))
            xy = np.column_stack(field.xy(table['ra'], table['dec']))
            stored.append((site, field, center, xy - center, table, meta))
            inputs.extend((truth, old / 'truth.json', receipt))
        first = stored[0]
        for _, _, _, offsets, table, meta in stored[1:]:
            if (not np.array_equal(table[['g0','r0']], first[4][['g0','r0']])
                    or not np.allclose(offsets, first[3], atol=1e-7, rtol=0)
                    or not np.isclose(meta['realized_MV_proxy'], first[5]['realized_MV_proxy'], atol=1e-12, rtol=0)):
                raise ValueError('Original populations and projected offsets are not shared')
        keep = np.ones(len(first[4]), dtype=bool)
        for _, _, center, offsets, _, meta in stored:
            for radius in RADII:
                scale = math.degrees(math.atan(radius / 100000)) * 60 / meta['theta_h_arcmin']
                keep &= np.hypot(*(center + offsets * scale).T) < splice - .03
        g, r = first[4]['g0'], first[4]['r0']
        luminosity = 10**(-.4 * (g - .59 * (g - r) - .01 - 20))
        retention.append(dict(parent_trial=parent, parent_N_imf=first[5]['N_imf'],
            parent_realized_MV_proxy=first[5]['realized_MV_proxy'], parent_N_rendered=len(g),
            common_stamp_N_rendered=int(keep.sum()), common_stamp_light_fraction=float(luminosity[keep].sum() / luminosity.sum()),
            common_stamp_MV_proxy=float(-2.5 * np.log10(luminosity[keep].sum()))))
        for site, field, center, offsets, table, meta in stored:
            name = site['field']
            site_dir = data / ('image-' + VERSION) / name
            site_dir.mkdir(parents=True, exist_ok=True)
            old_blank = data / 'image-v14_repeat' / name / 'blank'
            blank = site_dir / 'blank'
            if not blank.exists():
                blank.symlink_to(old_blank, target_is_directory=True)
            if blank.resolve() != old_blank.resolve():
                raise ValueError('Require the exact original blank CCD catalogue')
            _, blank_cat = native.native_table(blank)
            inputs.extend((blank_cat, blank / 'initial_detection.npy'))
            intrinsic = table[keep]
            old_ebv = reddening(intrinsic['ra'], intrinsic['dec'])
            for j, radius in enumerate(RADII):
                trial = 2 * k + j
                theta = math.degrees(math.atan(radius / 100000)) * 60
                sky = field.sky(*(center + offsets[keep] * theta / meta['theta_h_arcmin']).T)
                rerender = intrinsic.copy()
                rerender['ra'], rerender['dec'] = sky
                new_ebv = reddening(*sky)
                if not np.all(np.isfinite(old_ebv + new_ebv)):
                    raise ValueError('Invalid extinction on the common support')
                for b, coefficient in zip('griz', (3.214, 2.165, 1.592, 1.211)):
                    key = 'flux_' + b
                    rerender[key] *= 10**(-.4 * coefficient * (new_ebv - old_ebv))
                    if not np.allclose(rerender[key] * 10**(.4 * coefficient * new_ebv),
                                       intrinsic[key] * 10**(.4 * coefficient * old_ebv), rtol=1e-12, atol=0):
                        raise ValueError('Paired stellar fluxes changed')
                stage = site_dir / f'trial{trial:02d}'
                stage.mkdir(exist_ok=False)
                np.save(stage / 'truth.npy', rerender, allow_pickle=False)
                write_json(stage / 'truth.json', dict(meta, rh_pc=radius, theta_h_arcmin=theta, trial=trial,
                    parent_trial=parent, N_rendered=len(rerender), common_stamp_support=True))
                tasks.append(dict(task_index=len(tasks), site=name, trial=trial, parent_trial=parent, rh_pc=radius))
                inputs.extend([stage / 'truth.npy', stage / 'truth.json'])
    CONFIG.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    shutil.copyfile(PARENT / 'image_fields.csv', CONFIG / 'image_fields.csv')
    write_csv(OUTPUT / 'tasks.csv', tasks)
    write_csv(OUTPUT / 'population_support.csv', retention)
    inputs.extend((CONFIG / 'image_fields.csv', OUTPUT / 'tasks.csv', OUTPUT / 'population_support.csv'))
    write_json(OUTPUT / 'registration.json', dict(job=os.environ['SLURM_JOB_ID'], native_cases=len(tasks),
        parent_trials=parents, luminosity_ordinals_zero_based=LUMINOSITY_ORDINALS, splice_radius_arcmin=splice,
        source_sha256={str(path): sha(path) for path in inputs}, code_sha256=sha(Path(__file__)),
        scope='10 and 15 pc, same old stellar draws and members on common finite stamp support, fixed 100 kpc and target −3 proxy light. Original finite catalogue is retained and its extra common-support loss reported. Twelve real CCD images across three fixed backgrounds, paired by latent population. This does not measure a complete physical 15 pc selection surface.'))


def verify_registration():
    registration = read(OUTPUT / 'registration.json')
    if registration['code_sha256'] != sha(Path(__file__)):
        raise ValueError('Registered experiment code changed')
    for k, checksum in registration['source_sha256'].items():
        if sha(Path(k)) != checksum:
            raise ValueError('Input changed: ' + k)
    return registration


def execute(data, index):
    registration = verify_registration()
    task = read_csv(OUTPUT / 'tasks.csv')[index]
    sites = read_csv(CONFIG / 'image_fields.csv')
    name, number = task['site'], int(task['trial'])
    site = next(s for s in sites if s['field'] == name)
    out = OUTPUT / 'trials' / f'{name}-{number:02d}.json'
    if out.exists():
        for p, expected in read(out)['outputs_from_native_sha256'].items():
            if sha(Path(p)) != expected:
                raise ValueError('Previously verified native output changed')
        return
    os.environ['LS_SAT_IMAGE_VERSION'] = VERSION
    folder = data / ('image-' + VERSION) / name
    stage = folder / f'trial{number:02d}'
    files = ('injected_exposures.npy', 'initial_detection.npy')
    if not all((stage / f).exists() for f in files) or len(list(stage.glob('tractor/*/tractor-*.fits'))) != 1:
        subprocess.run(['bash', 'scripts/v13_native.sh', name, stage.name], check=True)
    stars, cat = native.native_table(stage)
    blank, blank_cat = native.native_table(folder / 'blank')
    truth = read(stage / 'truth.json')
    original = np.load(stage / 'truth.npy', allow_pickle=False)
    pos = np.column_stack([original['ra'], original['dec']])
    initial = np.load(stage / files[1], allow_pickle=False)
    blank_initial = np.load(folder / 'blank' / files[1], allow_pickle=False)
    baseline = read(BASE)
    _, deep = load_registration()
    root = Path(os.environ['LS_DR11_ROOT'])
    spec = next(r for r in yaml.safe_load(MATCHED.read_text())['fields'] if r['id'] == site['background'])
    spec = dict(spec, width=baseline['width_deg'], buffer_arcmin=baseline['buffer_arcmin'], role='injection_control')
    field, released, area, _ = field_cache(root, data, spec, baseline['configuration'], load_bricks(root, 'south'))
    exposed = (np.load(stage / files[0], allow_pickle=False)[:, :2] > 0).all(axis=1)
    exposed &= area[sample_pixels(field, area, *field.xy(*pos.T))]
    sky = np.column_stack([stars['RA'], stars['DEC']])
    blank_sky = np.column_stack([blank['RA'], blank['DEC']])
    novel = native.match_to(sky, blank_sky, .8, field) < 0
    linked = native.match_to(pos, sky[novel], .8, field)
    linked = np.where(linked >= 0, np.flatnonzero(novel)[np.maximum(linked, 0)], -1) if novel.any() else linked
    first = initial[native.match_to(initial, blank_initial, .8, field) < 0]
    detected = native.match_to(pos, first, .8, field) >= 0
    summaries = []
    for label, arm in (('baseline', baseline), ('deeper', deep)):
        cfg = arm['configuration']
        sample, _, _, _, chosen = select(stars, field, area, cfg)
        psf, selected = native.photometry(stars, linked, field, area, cfg)
        locus = load_isochrone(native.template_paths(data, cfg)[0])
        cmd = np.zeros(len(stars), dtype=bool)
        cmd[chosen] = CMD.top_hat(sample[:, 2:4], sample[:, 4:6], 20., locus[2])
        exterior = select(released, field, area, cfg)[0]
        catalog = native.replaced(field, site, exterior, sample, registration['splice_radius_arcmin'])
        outcome = native.blind(catalog, field, area, locus, cfg, truth, arm['cutoff'], diagnostics=True)
        summaries.append(dict(**task, arm=label, N_rendered=len(original), N_exposed=int(exposed.sum()),
            N_initial=int((exposed & detected).sum()), N_final=int((exposed & (linked >= 0)).sum()),
            N_psf=int((exposed & psf).sum()), N_used=int((exposed & selected).sum()),
            N_cmd=int((exposed & (linked >= 0) & cmd[np.maximum(linked, 0)]).sum()), **outcome))
    out.parent.mkdir(exist_ok=True)
    write_json(out, dict(job=os.environ['SLURM_JOB_ID'], outputs_from_native_sha256={str(p): sha(p) for p in
        (cat, blank_cat, stage / files[0], stage / files[1], stage / 'truth.npy', stage / 'truth.json')}, rows=summaries))
    print(dict(task=index, site=name, radius=truth['rh_pc'], baseline=summaries[0]['spatial'],
               deeper=summaries[1]['spatial']), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('register', 'execute'))
    p.add_argument('--index', type=int)
    a = p.parse_args()
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated compute CPUs')
    data = Path(os.environ['LS_SAT_DATA'])
    if a.action == 'register':
        register(data)
    else:
        execute(data, a.index)


if __name__ == '__main__':
    main()
