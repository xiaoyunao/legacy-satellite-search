"""Blind-scan faint-light images and compare identical bright-member truth lists."""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import joint_coverage
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from ls_satsearch.search import CMD, load_isochrone
from scripts import v13_image_trials as native
from scripts.v14_faint_light import prepare, VERSION, CONFIG, OUT


def measure(site):
    prepare()
    native_proof = OUT/(site+'-native.json')
    for path, checksum in json.loads(native_proof.read_text())['inputs'].items():
        if sha(Path(path)) != checksum:
            raise ValueError('Accepted faint-light native product changed')
    native.VERSION = VERSION; native.CONFIG = CONFIG
    native.OUTPUT = Path('results')/VERSION/'image_response'
    native.measure(site, diagnostics=True)
    root, data, cfg = settings()
    cfg = yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    plan = yaml.safe_load(Path('configs/v13/matched/south/matched.yaml').read_text())
    cfg.update(dm=plan['dm'], radii_arcmin=plan['radii_arcmin'], methods=['A'], review_budgets_deg2=plan['review_budgets_deg2'])
    model = load_isochrone(native.template_paths(data, cfg)[0])
    fieldinfo = next(r for r in read_csv(CONFIG/'image_fields.csv') if r['field'] == site)
    spec = next(r for r in plan['fields'] if r['id'] == fieldinfo['background'])
    spec = dict(spec, width=plan['width_deg'], buffer_arcmin=plan['buffer_arcmin'])
    field, _, lsarea, _ = field_cache(root, data, spec, cfg, load_bricks(root, 'south'))
    area = joint_coverage(field, lsarea, data/'resources/ps1/ps1d_mask_v2.1.fits')
    local = native.local_coordinates(fieldinfo)
    blankdir = data/'image-v14_repeat'/site/'blank'
    blank, blankcat = native.native_table(blankdir)
    blank_sky = np.column_stack([blank['RA'], blank['DEC']])
    outcomes = read_csv(native.OUTPUT/(site+'-blind.csv'))
    original = [r for r in read_csv(Path('results/v14_stamp_boundary/image_response')/(site+'-blind.csv')) if r['trial'] == '0']
    inputs = {str(OUT/'registration.json'):sha(OUT/'registration.json'), str(blankcat):sha(blankcat)}
    rows = []
    for arm in ('ls_base', 'ls_deep'):
        actual = cfg.copy()
        if arm == 'ls_deep':
            for band in 'gr': actual[band+'_max'] += .5
        for trial in (0, 1):
            folder = data/('image-'+VERSION)/site/f'trial{trial:02d}'
            meta = json.loads((folder/'truth.json').read_text())
            # Only unchanged bright-member identities enter this comparison.
            # Do not let numerous unobserved faint truths steal their associations.
            bright = np.load(folder/'truth.npy', allow_pickle=False)[:meta['N_bright_extended']]
            sample, cat = native.native_table(folder)
            sky = np.column_stack([sample['RA'], sample['DEC']])
            positions = np.column_stack([bright['ra'], bright['dec']])
            observed = (np.load(folder/'injected_exposures.npy', allow_pickle=False)[:len(bright), :2]>0).all(axis=1)
            observed &= area[sample_pixels(field, area, *field.xy(*positions.T))]
            novel = native.match_to(sky, blank_sky, .8, local) < 0
            found = native.match_to(positions, sky[novel], .8, local)
            linked = np.where(found>=0, np.flatnonzero(novel)[np.maximum(found, 0)], -1) if novel.any() else found
            psf, selected = native.photometry(sample, linked, field, area, actual)
            selected_sample, _, _, _, chosen = select(sample, field, area, actual)
            cmd = np.zeros(len(sample), bool)
            cmd[chosen] = CMD.top_hat(selected_sample[:, 2:4], selected_sample[:, 4:6], 20, model[2])
            on_cmd = (linked>=0) & cmd[np.maximum(linked, 0)]
            outcome = next(r for r in outcomes if r['arm'] == arm and int(r['trial']) == trial)
            row = dict(outcome, N_bright_rendered=len(bright), N_bright_exposed=int(observed.sum()),
                N_bright_final=int((observed & (linked>=0)).sum()), N_bright_psf=int((observed & psf).sum()),
                N_bright_used=int((observed & selected).sum()), N_bright_cmd=int((observed & on_cmd).sum()),
                variant='added_faint_light' if trial == 0 else 'extended_bright_control')
            if trial == 1:
                old = next(r for r in original if r['arm'] == arm)
                for key in ('N_exposed', 'N_final', 'N_psf', 'N_used', 'spatial', 'blind_dm', 'blind_correct', 'correct_mode_exists'):
                    if outcome[key] != old[key]: raise ValueError('Reused expanded-bright control changed: '+key)
                for key in ('exposed', 'final', 'psf', 'used'):
                    if row['N_bright_'+key] != int(old['N_'+key]): raise ValueError('Fixed bright-list control does not reproduce')
            rows.append(row)
            for p in (cat, folder/'truth.npy', folder/'truth.json', folder/'injected_exposures.npy'):
                inputs[str(p)] = sha(p)
    write_csv(OUT/(site+'-paired.csv'), rows)
    for p in (native.OUTPUT/(site+'-blind.csv'), Path('results/v14_stamp_boundary/image_response')/(site+'-blind.csv')):
        inputs[str(p)] = sha(p)
    write_json(OUT/(site+'-acceptance.json'), dict(job=os.environ['SLURM_JOB_ID'], paired_arm_cases=2,
        inputs=inputs, code_sha256=sha(Path(__file__)), unchanged_bright_members_measured_separately=True,
        original_extended_controls_reproduced=True,
        scope='One outcome-targeted near-boundary IMF realization across prespecified original backgrounds. '
              'Blind scanner receives measured catalogues, not truth centres. Bright-member associations use '
              'the unchanged bright list to prevent faint truth crowding from biasing the comparison. '
              'All-truth counts have a different denominator; retained separately. Native frame/splice fixed. '
              'New faint positions and changed photon pixels are included; no pure diffuse-light effect, '
              'full spatial IMF rendering, independent-population completeness or PS1 gain claim.'))
    print('FAINT_LIGHT_MEASUREMENT_ACCEPTED', site, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('site', choices=tuple('v14_south_response_'+str(i) for i in (1, 2, 3)))
    measure(p.parse_args().site)
