"""Check the six-panel layout on the frozen real, zero-group CCD control."""

import argparse
import os
from pathlib import Path

import numpy as np
import yaml

from ls_satsearch.data import select
from ls_satsearch.run import field_cache, settings, sha, write_json
from ls_satsearch.search import load_isochrone
from scripts.v14_production_deeper_replay import MATCHED, load_registration
from scripts.v14_review_science import render


def selected(raw, field, area, cfg):
    stars, _, valid, mags, _ = select(raw, field, area, cfg)
    extended = valid & np.isin(np.char.strip(raw['TYPE'].astype('U')), ('REX', 'EXP', 'DEV', 'SER'))
    sources = raw[extended]
    err = np.column_stack([2.5 / np.log(10) / (sources[f'FLUX_{b}'] * np.sqrt(sources[f'FLUX_IVAR_{b}']))
                           for b in 'GR'])
    galaxies = np.column_stack((*field.xy(sources['RA'], sources['DEC']), mags[extended], err))
    return stars, galaxies


def run(output):
    if not os.getenv('SLURM_JOB_ID') or 'final_private' not in output.parts:
        raise RuntimeError('Use allocated CPUs and private storage')
    os.environ['LS_SAT_IMAGE_VERSION'] = 'v14_repeat'
    from scripts import v13_image_trials as native

    name = 'v14_south_response_1'
    registration, frozen = load_registration()
    root, data, _ = settings()
    cfg = frozen['configuration']
    site, plan, _ = native.context(name)
    specs = yaml.safe_load(MATCHED.read_text())['fields']
    spec = next(r for r in specs if r['id'] == site['background'])
    spec = dict(spec, width=frozen['width_deg'], buffer_arcmin=frozen['buffer_arcmin'], role='injection_control')
    field, released, area, _ = field_cache(root, data, spec, cfg, None)
    blank, native_path = native.native_table(data / 'image-v14_repeat' / name / 'blank')
    outside, inside = selected(released, field, area, cfg), selected(blank, field, area, cfg)
    stars, galaxies = [native.replaced(field, site, a, b, plan['splice_radius_arcmin'])
                       for a, b in zip(outside, inside)]
    locus = load_isochrone(native.template_paths(data, cfg)[0])[2]
    mode = dict(fit_ra_deg=site['ra_deg'], fit_dec_deg=site['dec_deg'], fit_dm=20., fit_rh_arcmin=1.)
    output.mkdir(exist_ok=False)
    results = {}
    for sigma in (.5, 2.):
        path = output / f'blank_sigma{sigma:g}.png'
        metrics = render(path, field, area, stars, galaxies, locus, mode, None, None, sigma,
                         g_limit=cfg['g_max'])
        results[path.name] = dict(metrics, sha256=sha(path))
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'],
        baseline_registration_sha256=sha(registration), native_blank_catalogue_sha256=sha(native_path),
        outputs=results, frozen_baseline_qualifying_groups=0))
    print(dict(blank_panels=len(results), core_cmd_count=metrics['core_cmd_count']), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    run(p.parse_args().output)
