"""Bound association-algorithm loss using existing native catalogues only."""
import os
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import joint_coverage
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from scripts import v13_image_trials as native
from scripts.v14_paired_radius import prepare, CONFIG, OUT


def maximum_count(truth_xy, source_xy, radius):
    if not len(truth_xy) or not len(source_xy): return 0
    neighbors = cKDTree(source_xy).query_ball_point(truth_xy, radius/60)
    ri, ci = [], []
    for i, values in enumerate(neighbors):
        ri.extend([i]*len(values)); ci.extend(values)
    graph = csr_matrix((np.ones(len(ri), dtype=np.int8), (ri, ci)), shape=(len(truth_xy), len(source_xy)))
    return int((maximum_bipartite_matching(graph, perm_type='column') >= 0).sum())


def run():
    if not os.getenv('SLURM_JOB_ID'): raise ValueError('Read native catalogues on compute nodes')
    prepare(); root, data, _ = settings()
    cfg = yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    plan = yaml.safe_load(Path('configs/v13/matched/south/matched.yaml').read_text())
    sites = {r['field']:r for r in read_csv(CONFIG/'image_fields.csv')}
    tasks = read_csv(CONFIG/'tasks.csv')
    stages = {(r['site'], int(r['new_trial']), r['arm']):r for r in read_csv(OUT/'full_stage_pairs.csv')}
    inputs = {str(OUT/'full_stage_acceptance.json'):sha(OUT/'full_stage_acceptance.json')}
    rows = []; core_counts = []; fields = {}; bricks = load_bricks(root, 'south')
    for task in tasks:
        site = sites[task['site']]; name = site['field']; local = native.local_coordinates(site)
        if name not in fields:
            spec = next(r for r in plan['fields'] if r['id']==site['background'])
            spec = dict(spec, width=plan['width_deg'], buffer_arcmin=plan['buffer_arcmin'])
            field, _, mask, _ = field_cache(root, data, spec, cfg, bricks)
            fields[name] = (field, joint_coverage(field, mask, data/'resources/ps1/ps1d_mask_v2.1.fits'))
        field, area = fields[name]
        blank_folder = data/'image-v14_repeat'/name/'blank'
        blank, blank_cat = native.native_table(blank_folder)
        blank_sky = np.column_stack([blank['RA'], blank['DEC']])
        blank_xy = np.column_stack(local.xy(*blank_sky.T))
        inputs[str(blank_cat)] = sha(blank_cat)
        for variant, folder in (
                ('parent10', data/'image-v14_repeat'/name/f'trial{int(task["original_trial"]):02d}'),
                ('paired3', data/'image-v14_paired_radius'/name/f'trial{int(task["new_trial"]):02d}')):
            truth = np.load(folder/'truth.npy', allow_pickle=False)
            meta = json.loads((folder/'truth.json').read_text())
            sample, cat = native.native_table(folder)
            sky = np.column_stack([sample['RA'], sample['DEC']]); xy = np.column_stack(local.xy(*sky.T))
            pos = np.column_stack([truth['ra'], truth['dec']]); txy = np.column_stack(local.xy(*pos.T))
            exposed = (np.load(folder/'injected_exposures.npy', allow_pickle=False)[:, :2]>0).all(axis=1)
            exposed &= area[sample_pixels(field, area, *field.xy(*pos.T))]
            novel = native.match_to(sky, blank_sky, .8, local)<0
            point = np.char.strip(sample['TYPE'].astype(str))=='PSF'
            found = native.match_to(pos, sky[novel], .8, local)
            linked = np.where(found>=0, np.flatnonzero(novel)[np.maximum(found, 0)], -1) if novel.any() else found
            center = np.asarray(local.xy(meta['truth_ra_deg'], meta['truth_dec_deg']))
            core = np.linalg.norm(xy-center, axis=1)<3*meta['theta_h_arcmin']
            blank_core = np.linalg.norm(blank_xy-center, axis=1)<3*meta['theta_h_arcmin']
            for arm in ('ls_base', 'ls_deep'):
                actual = cfg.copy()
                if arm=='ls_deep':
                    for band in 'gr': actual[band+'_max'] += .5
                chosen = select(sample, field, area, actual)[4]
                psf, used = native.photometry(sample, linked, field, area, actual)
                reference = stages[name, int(task['new_trial']), arm]
                greedy = dict(final=int((exposed & (linked>=0)).sum()), psf=int((exposed & psf).sum()), used=int((exposed & used).sum()))
                if any(greedy[key]!=int(reference[variant+'_N_'+key]) for key in greedy):
                    raise ValueError('Original0.8arcsec stage counts do not reproduce')
                core_counts.append(dict(site=name, original_trial=task['original_trial'], variant=variant, arm=arm,
                    radius_in_rh=3, catalogue_sources=int(core.sum()), blank_sources=int(blank_core.sum()),
                    catalogue_minus_blank=int(core.sum()-blank_core.sum()), novel_sources=int((core & novel).sum()),
                    novel_PSF=int((core & novel & point).sum()), novel_hard=int((core & novel & chosen).sum())))
                for radius in (.4, .8, 1.6):
                    record = dict(site=name, original_trial=task['original_trial'], variant=variant, arm=arm,
                        radius_arcsec=radius, exposed_truth=int(exposed.sum()), greedy_final_at0p8=greedy['final'],
                        greedy_psf_at0p8=greedy['psf'], greedy_used_at0p8=greedy['used'])
                    for key, eligible in [('final', novel), ('psf', novel & point), ('used', novel & chosen)]:
                        record['maximum_'+key] = maximum_count(txy[exposed], xy[eligible], radius)
                    if radius==.8 and record['maximum_final']<greedy['final']:
                        raise ValueError('Maximum matching cannot recover fewer associations')
                    rows.append(record)
            for p in (cat, folder/'truth.npy', folder/'truth.json', folder/'injected_exposures.npy'):
                inputs[str(p)] = sha(p)
    if any(sha(Path(p))!=v for p,v in inputs.items()): raise ValueError('Audit input changed')
    write_csv(OUT/'association_bounds.csv', rows); write_csv(OUT/'core_source_counts.csv', core_counts)
    write_json(OUT/'association_acceptance.json', dict(job=os.environ['SLURM_JOB_ID'], inputs=inputs,
        code_sha256=sha(Path(__file__)), registered_native_pairs=len(tasks), original0p8_stage_counts_reproduced=True,
        scope='Postprocessing only; native images/catalogues, detector/cuts and original144 outcomes unchanged. '
              'Novel-source versus blank definition stays0.8arcsec. Maximum cardinality counts observed truths '
              'against eligible catalogue objects separately for all/PSF/hard subsets, giving association '
              'upper bounds rather than a single joint assignment.1.6arcsec may include chance alignments. '
              'Core counts within3rh do not use injected truth identities for matching. No new Pdet or pure '
              'crowding decomposition; compare relative source excess and association bounds.'))
    print('PAIRED_RADIUS_ASSOCIATION_AUDIT_ACCEPTED', len(rows), flush=True)


if __name__=='__main__': run()
