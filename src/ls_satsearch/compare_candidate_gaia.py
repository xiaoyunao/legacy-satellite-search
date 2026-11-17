"""Same-centre LS and PS1 CMD tests before and after a common Gaia veto."""

import argparse
import csv
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import binom
import yaml

from .candidate_archives import frozen_positions
from .data import Field, sample_pixels, select
from .matched import PS1_MODEL, joint_coverage
from .run import sha, write_csv, write_json
from .search import CMD, exact_onoff, load_isochrone, point_fit
from .verify_candidate import ps1_sample, setup


def known_foreground(rows, plan):
    reliable = [r for r in rows if r['ruwe'] and
                float(r['ruwe']) < plan['foreground_ruwe_max'] and r['parallax_error'] and
                0 < float(r['parallax_error'])]
    foreground = [r for r in reliable if float(r['parallax']) >
                  max(plan['foreground_min_parallax_mas'],
                      plan['foreground_min_parallax_snr']*float(r['parallax_error']))]
    return reliable, foreground


def coords(rows):
    return SkyCoord([float(r['ra']) for r in rows],[float(r['dec']) for r in rows],unit='deg')


def separation_mask(sample, field, rows, radius):
    if not rows:
        return np.zeros(len(sample),dtype=bool)
    sky = SkyCoord(*field.sky(*sample[:,:2].T),unit='deg')
    return sky.match_to_catalog_sky(coords(rows))[1].arcsec <= radius


def fixed_case(sample, model, field, mask, cfg, dm, rh):
    cmd = CMD(sample, model, cfg)
    locus, ratio = cmd.weights(dm)
    tree = cKDTree(sample[:,:2])
    on,off,on_area,off_area = exact_onoff(field,0.,0.,rh,tree,mask,locus)
    fit, _, _ = point_fit(sample,cmd,field,mask,dict(x=0.,y=0.,dm=dm,rh_arcmin=rh),ratio=ratio)
    return dict(on=int(on),off=int(off),on_area_arcmin2=float(on_area),off_area_arcmin2=float(off_area),
                binomial_tail=float(binom.sf(on-1,on+off,on_area/(on_area+off_area))),
                C_TS=fit['ts'] if fit else None,C_richness=fit['richness'] if fit else None)


def run(policy):
    rule = yaml.safe_load(policy.read_text())
    plan,ls_config,data,old,sources,old_mask = setup(Path(rule['followup']) if 'followup' in rule else None)
    if plan['candidate'] != rule['candidate']:
        raise ValueError('Candidate differs from frozen evidence')
    field = Field(plan['ra_deg'],plan['dec_deg'],plan['ps1_scan_width_deg'],
                  min(plan['ps1_scan_radii'])/3,buffer=plan['ps1_scan_buffer_arcmin'])
    subdivision = ls_config['coverage_subdivision']
    n = field.n*subdivision
    axis = (np.arange(n)+.5)*2*field.limit/n-field.limit
    x,y = np.meshgrid(axis,axis)
    ra,dec = field.sky(x,y)
    mask = old_mask[sample_pixels(old,old_mask,*old.xy(ra,dec))]
    mask &= np.hypot(x,y) < 60*plan['ps1_radius_deg']
    mask = joint_coverage(field,mask,data/'resources/ps1/ps1d_mask_v2.1.fits')
    xx,yy = field.xy(sources['RA'],sources['DEC'])
    keep = np.hypot(xx,yy) < 60*plan['ps1_radius_deg']
    ls, *_ = select(sources[keep],field,mask,ls_config)
    cache = data/'resources'/plan.get('scratch_revision','v6')/plan['candidate']
    ps1, ps_input = ps1_sample(plan,field,mask,cache)
    ps_cfg = dict(ls_config,g_max=plan['ps1_magnitude_caps'][0],r_max=plan['ps1_magnitude_caps'][1])
    inputs = data/'resources'
    models = {'LS':load_isochrone(inputs/ls_config['isochrone']),
              'PS1':load_isochrone(inputs/PS1_MODEL,bands=('gP1','rP1'))}

    with (cache/'gaia-wide.csv').open(newline='') as stream:
        gaia_rows = list(csv.DictReader(stream))
    _, foreground = known_foreground(gaia_rows,rule)
    with (cache/'gaia-astrometry.csv').open(newline='') as stream:
        astrometry = list(csv.DictReader(stream))
    radius = rule['gaia_match_arcsec']
    positions = frozen_positions(plan,data,sources)
    idx,sep,_ = positions.match_to_catalog_sky(coords(astrometry))
    matched = [astrometry[i] for i in sorted(set(idx[sep.arcsec<=radius]))]
    reliable, identified = known_foreground(matched,rule)
    discrepant = [r for r in reliable if r not in identified and r['pmra'] and r['pmdec']]
    if 'followup' in rule:
        discrepant = []
        qso_path = cache/'desi-qso-veto.json'
        qso = json.loads(qso_path.read_text())
    elif len(discrepant)!=2:
        raise ValueError('Expected the two previously identified discrepant bright stars')
    else:
        qso_path, qso = None, []

    rows = []
    for survey,sample,cfg in (('LS',ls,ls_config),('PS1',ps1,ps_cfg)):
        veto = separation_mask(sample,field,foreground,radius)
        exclude_pair = separation_mask(sample,field,discrepant,radius)
        selections = [('original',np.ones(len(sample),dtype=bool)),('uniform_foreground_veto',~veto)]
        if discrepant:
            selections.append(('also_exclude_discrepant_pair',~(veto | exclude_pair)))
        if qso:
            excluded_qso = separation_mask(sample,field,qso,radius)
            selections.append(('also_exclude_secure_desi_qso',~(veto | excluded_qso)))
        brightening = rule.get('sensitivity_brightening_mag')
        if brightening is not None:
            brighter = np.all(sample[:,2:4]<=np.array([cfg['g_max'],cfg['r_max']])-brightening,axis=1)
            selections.append(('gaia_veto_brighter_caps', ~veto & brighter))
        obs = dict(matched_desi_qso=int(excluded_qso.sum())) if qso else {}
        for label, retained in selections:
            for dm in rule['fixed_dm']:
                cfg_at_cut = dict(cfg,g_max=cfg['g_max']-brightening,r_max=cfg['r_max']-brightening
                                  ) if label=='gaia_veto_brighter_caps' else cfg
                rows.append(dict(survey=survey,selection=label,dm=dm,
                                 selected=int(retained.sum()),matched_foreground=int(veto.sum()),
                                 discrepant_pair_matches=int(exclude_pair.sum()),**obs,
                                 **fixed_case(sample[retained],models[survey],field,mask,cfg_at_cut,dm,
                                              rule['half_light_arcmin'])))
    default_output = 'results/v8/survey14' if 'followup' in rule else 'results/verification'
    out = Path(rule.get('output',default_output))
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'ls_ps1_same_gaia_veto.csv',rows)
    write_json(out/'ls_ps1_same_gaia_veto.json',dict(job=os.environ.get('SLURM_JOB_ID'),
               config=sha(policy),wide_gaia_sha256=sha(cache/'gaia-wide.csv'),
               pair_gaia_sha256=sha(cache/'gaia-astrometry.csv'),ps1=ps_input,
               desi_qso_veto_sha256=sha(qso_path) if qso_path else None,
               joint_area_deg2=float(mask.sum()*(field.step/subdivision/60)**2)))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,default=Path('configs/v7/candidate.yaml'))
    run(parser.parse_args().policy)
