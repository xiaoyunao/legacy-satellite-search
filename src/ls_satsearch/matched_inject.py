"""Observe common latent stellar populations in the matched catalog samples."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .data import sample_pixels
from .group_budget import groups, matches
from .inject import choose_sites, observe
from .matched import DEST, PS1_MODEL, SURVEYS
from .ps1_tiles import design
from .run import config_path, read_csv, runs_path, settings, sha, write_csv, write_json
from .search import load_isochrone, scan

import yaml


def run(field_id):
    _,data_root,cfg = settings()
    matched = yaml.safe_load(config_path('matched.yaml').read_text())
    spec = next(s for s in matched['fields'] if s['id']==field_id and s['role']=='pilot_dev')
    field,_ = design(spec,matched)
    models = {}
    samples = {}
    manifests = {}
    cuts = {}
    paths = [data_root/'resources'/model for model in (cfg['isochrone'], PS1_MODEL)]
    # Pin the physical row correspondence before sharing IMF/phase draws across systems.
    signatures = [np.loadtxt(p,usecols=(0,1,2,3,4,5,6,7,14,15)) for p in paths]
    if not np.array_equal(*signatures):
        raise ValueError('PARSEC physical rows are not identical between catalogs')
    ls_model = load_isochrone(paths[0])
    for survey in SURVEYS:
        work = runs_path(data_root)/'matched'/survey/field_id
        samples[survey] = np.load(work/'sample.npy',allow_pickle=False)
        coverage = np.load(work/'coverage.npy',allow_pickle=False)
        if survey == 'ls_base':
            area = coverage
        if not np.array_equal(coverage,area):
            raise ValueError('Surveys do not share the same pixel mask')
        models[survey] = load_isochrone(paths[1],bands=('gP1','rP1')) if survey=='ps1' else ls_model
        name = DEST/survey/'summary'/f'{field_id}-base'
        manifests[survey] = json.loads((name/'manifest.json').read_text())
        policy = json.loads((DEST/survey/'groups/sky_group_policy.json').read_text())
        cuts[survey] = next(row['cutoff'] for row in policy['thresholds'] if row['policy']=='A_base')
        if cuts[survey] is None:
            raise ValueError('The shared review budget has no calibrated cutoff')
    trees = {survey:cKDTree(sample[:,:2]) for survey,sample in samples.items()}
    seed = [cfg['seed'],int(spec['ra']*1000),34]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    positions = choose_sites(field,area,cfg,2,rng)
    trials = []
    for index,(pos,(distance,stars)) in enumerate(zip(positions,[(50,28),(100,40)])):
        rh = np.degrees(np.arctan(.03/distance))*60
        dm = 5*np.log10(distance)+10
        # Define a common parent conditional LF from the union of the faint windows.
        included = np.zeros(len(ls_model[0]),dtype=bool)
        for survey,model in models.items():
            c = manifests[survey]['config']
            included |= np.all(model[0]+dm <= np.array([c['g_max'],c['r_max']])+.4,axis=1)
        weights = ls_model[1]*included
        drawn = rng.choice(len(weights),stars,p=weights/weights.sum())
        q = rng.uniform(0,.9,stars)
        angle = rng.uniform(0,2*np.pi,stars)
        xy = pos + rh*np.sqrt(q/(1-q))[:,None]*np.column_stack([np.cos(angle),np.sin(angle)])
        in_area = area[sample_pixels(field,area,*xy.T)]
        ra,dec = field.sky(*pos)
        truth = dict(ra_deg=ra,dec_deg=dec,theta_h_arcmin=rh,D_kpc=distance)
        ls_obs = observe(ls_model[0][drawn]+dm,pos,rng,manifests['ls_deep']['config'],
                         samples['ls_deep'],trees['ls_deep'])
        for survey in SURVEYS:
            c = manifests[survey]['config']
            if survey == 'ps1':
                phot,sig,selected = observe(models[survey][0][drawn]+dm,pos,rng,c,samples[survey],trees[survey])
            else:
                phot,sig,selected = ls_obs
                selected = selected & np.all(phot <= [c['g_max'],c['r_max']],axis=1)
            delivered = np.column_stack([xy,phot,sig])[selected & in_area]
            archive = DEST/survey/'summary'/f'{field_id}-base/deduplicated_peaks.csv'
            blank = [{k:float(r[k]) for k in ('x','y','dm','rh_arcmin','ra_deg','dec_deg','score')}
                     for r in read_csv(archive) if r['method']=='A' and r['branch']=='main'
                     and float(r['score'])>=cuts[survey]]
            _,peaks,timing,_ = scan(np.vstack([samples[survey],delivered]),field,area,models[survey],c)
            scanned = [r for r in peaks if r['score']>=cuts[survey]]
            blank_match,injected_match = (matches(groups([dict(p,channel='A_base',ranking=p['score'])
                          for p in choices]),truth,cuts[survey],c) for choices in (blank,scanned))
            trials.append(dict(field=field_id,trial=index,survey=survey,D_kpc=distance,rh_pc=30,
                               N_generated=stars,N_after_selection=int(selected.sum()),
                               N_in_valid_area=int(in_area.sum()),N_used=len(delivered),
                               blank_spatial=blank_match['spatial'],cutoff=cuts[survey],
                               seconds=sum(timing.values()),**injected_match))
    dest = DEST/'injections'
    dest.mkdir(exist_ok=True,parents=True)
    write_csv(dest/f'{field_id}.csv',trials)
    write_json(dest/f'{field_id}.json',dict(status='complete',seed=seed,job=os.environ.get('SLURM_JOB_ID'),
               model_sha256=[sha(p) for p in paths],
               selection='Conditional catalog injection. Morphology/measurement completeness is unmodeled.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field')
    run(parser.parse_args().field)
