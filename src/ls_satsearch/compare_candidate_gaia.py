"""Same-centre LS and PS1 CMD tests before and after a common Gaia veto."""

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


def run():
    policy = Path('configs/v7/candidate.yaml')
    rule = yaml.safe_load(policy.read_text())
    plan,ls_config,data,old,sources,old_mask = setup()
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
    cache = data/'resources/v6'/plan['candidate']
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
    if len(discrepant)!=2:
        raise ValueError('Expected the two previously identified discrepant bright stars')

    rows = []
    for survey,sample,cfg in (('LS',ls,ls_config),('PS1',ps1,ps_cfg)):
        veto = separation_mask(sample,field,foreground,radius)
        exclude_pair = separation_mask(sample,field,discrepant,radius)
        for label, retained in (('original',np.ones(len(sample),dtype=bool)),
                                ('uniform_foreground_veto',~veto),
                                ('also_exclude_discrepant_pair',~(veto | exclude_pair))):
            for dm in rule['fixed_dm']:
                rows.append(dict(survey=survey,selection=label,dm=dm,
                                 selected=int(retained.sum()),matched_foreground=int(veto.sum()),
                                 discrepant_pair_matches=int(exclude_pair.sum()),
                                 **fixed_case(sample[retained],models[survey],field,mask,cfg,dm,
                                              rule['half_light_arcmin'])))
    out = Path('results/verification')
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'ls_ps1_same_gaia_veto.csv',rows)
    write_json(out/'ls_ps1_same_gaia_veto.json',dict(job=os.environ.get('SLURM_JOB_ID'),
               config=sha(policy),wide_gaia_sha256=sha(cache/'gaia-wide.csv'),
               pair_gaia_sha256=sha(cache/'gaia-astrometry.csv'),ps1=ps_input,
               joint_area_deg2=float(mask.sum()*(field.step/subdivision/60)**2)))


if __name__=='__main__':
    run()
