"""Add omitted faint IMF light to the already registered near-boundary system."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import yaml

from ls_satsearch.matched import reddening
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone
from scripts.v13_image_trials import local_coordinates, template_paths
from scripts.v14_repeat_population_audit import replay

VERSION = 'v14_faint_light'
CONFIG = Path('configs') / VERSION
OUT = Path('results/v14/faint_light')
TRIAL = 34
RADIUS = 3.1


def prepare():
    if not os.getenv('SLURM_JOB_ID'):
        raise ValueError('Native truth/SFD work requires compute allocation')
    registration = OUT / 'registration.json'
    if registration.exists():
        for name, checksum in json.loads(registration.read_text())['inputs'].items():
            if sha(Path(name)) != checksum:
                raise ValueError('Frozen faint-light input changed: ' + name)
        return
    data = Path(os.environ['LS_SAT_DATA'])
    planpath = Path('configs/v14_repeat/image_trials.yaml')
    plan = yaml.safe_load(planpath.read_text())
    cfg = yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    modelpath, decpath = template_paths(data, cfg)
    model, decam = load_isochrone(modelpath), load_isochrone(decpath)
    eligible_ids, xy, keep, draw, proxy, center = replay(plan, TRIAL, model, decam)
    valid = np.any(np.column_stack([model[0], decam[0]]) < np.array([26, 25.5]*2)-20, axis=1)
    faint_ids = np.repeat(np.arange(len(draw)), draw * ~valid)
    # These stars were never assigned positions in the original generator.
    # Draw conditional omitted-member positions without altering any old star.
    rng = np.random.default_rng([plan['seed'], TRIAL, 5571])
    q = rng.random(len(faint_ids)); angle = rng.uniform(0, 2*np.pi, len(faint_ids))
    arc = np.rad2deg(np.arctan(30/100000))*60
    faint_xy = center + (arc*np.sqrt(q/(1-q)))[:, None] * np.column_stack([np.cos(angle), np.sin(angle)])
    inside = np.linalg.norm(faint_xy, axis=1) < RADIUS-.03
    ids, positions = faint_ids[inside], faint_xy[inside]
    with modelpath.open() as stream:
        columns = next(line[1:].split() for line in stream if line.startswith('#') and 'int_IMF' in line)
    mags = np.column_stack([model[0], np.loadtxt(modelpath, usecols=[columns.index(b) for b in ('i', 'z')])])
    ps1path = data/'resources'/plan['ps1_template']
    ps1 = load_isochrone(ps1path, bands=('gP1', 'rP1'))
    with ps1path.open() as stream:
        columns = next(line[1:].split() for line in stream if line.startswith('#') and 'int_IMF' in line)
    ps1mags = np.column_stack([ps1[0], np.loadtxt(ps1path, usecols=columns.index('iP1'))])
    boundary = Path('results/v14/stamp_boundary/acceptance.json')
    accepted = json.loads(boundary.read_text())
    for path, checksum in accepted['input_sha256'].items():
        if sha(Path(path)) != checksum:
            raise ValueError('Accepted boundary diagnostic changed')
    sites = read_csv(Path('configs/v14_repeat/image_fields.csv'))
    CONFIG.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    inputs = [Path(__file__), Path('scripts/v14_faint_light.sh'), Path('configs/v14_faint_light/protocol.yaml'),
              planpath, modelpath, decpath, ps1path, boundary,
              Path('scripts/v13_native.py'), Path('scripts/v13_native.sh'),
              Path('scripts/v13_image_trials.py'), Path('scripts/v14_repeat_population_audit.py')]
    counts = []
    for site in sites:
        name = site['field']; field = local_coordinates(site)
        old = data/'image-v14_stamp_boundary'/name/'trial00'
        core = np.load(old/'truth.npy', allow_pickle=False); meta = json.loads((old/'truth.json').read_text())
        # Original magnitude-eligible stars and expanded-footprint positions must reproduce.
        extended = np.linalg.norm(xy, axis=1) < RADIUS-.03
        ordered_ids = np.concatenate([eligible_ids[keep], eligible_ids[extended & ~keep]])
        ordered_xy = np.concatenate([xy[keep], xy[extended & ~keep]])
        if (len(core) != int(extended.sum()) or not np.array_equal(core['g0'], mags[ordered_ids, 0]+20)
                or not np.allclose(np.column_stack(field.xy(core['ra'], core['dec'])), ordered_xy, atol=1e-7, rtol=0)):
            raise ValueError('Accepted extended bright-member population differs')
        ra, dec = field.sky(*positions.T); ebv = reddening(ra, dec)
        extra = np.empty(len(ids), dtype=core.dtype); extra['ra'], extra['dec'] = ra, dec
        extra['g0'], extra['r0'] = (mags[ids, :2]+20).T
        observed = mags[ids]+20+ebv[:, None]*[3.214, 2.165, 1.592, 1.211]
        for k, band in enumerate('griz'):
            extra['flux_'+band] = 10**(-.4*(observed[:, k]-22.5))
        for k, band in enumerate('gri'):
            extra['ps1_'+band+'0'] = ps1mags[ids, k]+20
        base = data/('image-'+VERSION)/name; base.mkdir(parents=True, exist_ok=True)
        for number, table in ((0, np.concatenate([core, extra])), (1, core)):
            folder = base/f'trial{number:02d}'; folder.mkdir(exist_ok=True)
            np.save(folder/'truth.npy', table, allow_pickle=False)
            write_json(folder/'truth.json', dict(meta, trial=number, N_rendered=len(table),
                original_trial=TRIAL, latent_population_id=TRIAL,
                source_poisson_seed=meta.get('source_poisson_seed', 483423),
                N_bright_extended=len(core), N_faint_added=len(table)-len(core),
                faint_position_seed=[plan['seed'], TRIAL, 5571],
                scope='Conditional faint IMF positions within same finite3.1arcmin footprint; original bright members unchanged. Residual outer light remains unrendered.'))
            if number == 1:
                for item in ('tractor', 'injected_exposures.npy', 'initial_detection.npy'):
                    (folder/item).symlink_to(old/item, target_is_directory=item=='tractor')
            inputs.extend([folder/'truth.npy', folder/'truth.json'])
        (base/'blank').symlink_to(data/'image-v14_repeat'/name/'blank', target_is_directory=True)
        cat, = old.glob('tractor/*/tractor-*.fits')
        inputs.extend([old/'truth.npy', old/'truth.json', cat])
        bright_light = float(proxy[eligible_ids[extended]].sum())
        counts.append(dict(site=name, original_trial=TRIAL, N_imf=int(draw.sum()),
            N_bright_extended=len(core), N_faint_added=len(extra), N_all_within_footprint=len(core)+len(extra),
            full_IMF_light_proxy=float(draw@proxy), rendered_bright_light_proxy=bright_light,
            added_faint_light_proxy=float(proxy[ids].sum()),
            residual_unrendered_light_proxy=float(draw@proxy)-bright_light-float(proxy[ids].sum()),
            N_faint_outside_footprint=int((~inside).sum()),
            faint_position_assignment='New conditional draw, same IMF counts; not a replay of previously nonexistent faint-star positions'))
    write_csv(CONFIG/'image_fields.csv', sites)
    (CONFIG/'image_trials.yaml').write_text(yaml.safe_dump(dict(plan, conditions=[plan['conditions'][TRIAL]]*2,
        splice_radius_arcmin=RADIUS), sort_keys=False))
    inputs.extend([CONFIG/'image_fields.csv', CONFIG/'image_trials.yaml'])
    write_csv(OUT/'population_registration.csv', counts)
    write_json(registration, dict(job=os.environ['SLURM_JOB_ID'], inputs={str(p):sha(p) for p in inputs},
        original_trial=TRIAL, backgrounds=3, new_native_cases=3, old_control_reused=True,
        selection='Previously selected unique mixed-baseline bright30pc draw34; all three original skies, no outcome-dependent selection among them.',
        primary144_unchanged=True,
        scope='Near-boundary omitted-faint-light sensitivity at fixed IMF counts and unchanged bright members. Compare with accepted extended-bright control on identical native frame/splice. Includes conditional faint-star positions and changed source photon pixels. Residual infinite-profile tails remain; no complete-population correction or broad physical completeness.'))
    print('FAINT_LIGHT_REGISTERED', counts, flush=True)


def native(site):
    prepare()
    folder = Path(os.environ['LS_SAT_DATA'])/('image-'+VERSION)/site/'trial00'
    if not any(folder.glob('tractor/*/tractor-*.fits')):
        subprocess.run(['bash', 'scripts/v13_native.sh', site, 'trial00'], check=True)
    cat, = folder.glob('tractor/*/tractor-*.fits')
    table = np.load(folder/'truth.npy', allow_pickle=False)
    exposed = np.load(folder/'injected_exposures.npy', allow_pickle=False)
    if exposed.shape != (len(table), 4) or not (folder/'initial_detection.npy').is_file():
        raise ValueError('Native products incomplete')
    write_json(OUT/(site+'-native.json'), dict(job=os.environ['SLURM_JOB_ID'],
        inputs={str(p):sha(p) for p in (cat, folder/'truth.npy', folder/'truth.json',
                folder/'injected_exposures.npy', folder/'initial_detection.npy')}))
    print('FAINT_LIGHT_NATIVE_ACCEPTED', site, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'native'))
    parser.add_argument('--site', choices=tuple('v14_south_response_'+str(i) for i in (1, 2, 3)))
    args = parser.parse_args()
    if args.mode == 'prepare': prepare()
    elif args.site: native(args.site)
    else: parser.error('native requires --site')
