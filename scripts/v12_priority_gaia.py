"""Measure Gaia astrometric consistency of the fixed LS near-mode sample."""

import argparse
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np
from scipy.stats import chi2
import yaml

from ls_satsearch.candidate_archives import GAIA, GAIA_MIRROR, tap
from ls_satsearch.data import select
from ls_satsearch.run import field_cache, settings, sha, write_json
from ls_satsearch.search import CMD, load_isochrone, point_fit


COLUMNS=('ra','dec','pmra','pmdec','pmra_error','pmdec_error','parallax','parallax_error',
         'ruwe','phot_g_mean_mag')


def motion_statistic(rows):
    pm=rows[...,2:4]
    var=rows[...,4:6]**2+.15**2
    avg=np.sum(pm/var,axis=-2)/np.sum(1/var,axis=-2)
    statistic=np.sum((pm-avg[...,None,:])**2/var,axis=(-2,-1))
    return avg,statistic


def controls(members, reference, statistic, rng):
    n=len(members)
    pool=[np.flatnonzero(abs(reference[:,9]-g)<.6) for g in members[:,9]]
    if any(len(group)<8 for group in pool):
        return dict(control_status='insufficient magnitude-matched stars',
                    control_pool_sizes=[len(g) for g in pool])
    draws=np.empty((4096,n),dtype=int)
    for i in range(len(draws)):
        used=set()
        for j,group in enumerate(pool):
            pick=int(rng.choice(group))
            while pick in used:
                pick=int(rng.choice(group))
            used.add(pick)
            draws[i,j]=pick
    _,scores=motion_statistic(reference[draws])
    k=int((scores<=statistic).sum())
    return dict(control_status='complete',n_random_groups=len(scores),n_at_least_as_coherent=k,
                empirical_tail=(k+1)/(len(scores)+1),control_pool_sizes=[len(g) for g in pool])


def run(plan, output):
    root,data,_=settings()
    spec=yaml.safe_load(plan.read_text())
    ra,dec=spec['ra_deg'],spec['dec_deg']
    archive=Path(spec['field_manifest'])
    m=json.loads(archive.read_text())
    cfg=m['config']
    field,src,area,_=field_cache(root,data,m['field'],cfg,None)
    x,y=field.xy(ra,dec)
    sample,*_=select(src,field,area,cfg)
    model=load_isochrone(data/'resources'/cfg['isochrone'])
    peak=dict(x=x,y=y,dm=spec['dm'],rh_arcmin=spec['rh_arcmin'])
    cmd=CMD(sample,model,cfg)
    fit,idx,p=point_fit(sample,cmd,field,area,peak)
    if fit is None:
        raise ValueError('Fixed mode fit unavailable')
    cache=data/'resources'/spec['scratch_revision']/spec['candidate']/'gaia-kinematics.csv'
    q=','.join(COLUMNS)
    query=(f'SELECT TOP 10000 {q} FROM gaiadr3.gaia_source WHERE '
           f'1=CONTAINS(POINT(ra,dec),CIRCLE({ra},{dec},0.20))')
    site=GAIA
    try:
        native=tap(site,query,COLUMNS,cache,'GET')
    except (OSError,ValueError):
        site=GAIA_MIRROR
        native=tap(site,query,COLUMNS,cache,'GET')
    if len(native)==10000 or not native:
        raise ValueError('Gaia query truncated or empty')
    table=np.array([[float(r[k] or 'nan') for k in COLUMNS] for r in native])
    coords=SkyCoord(*field.sky(*sample[idx,:2].T),unit='deg')
    pos=SkyCoord(table[:,0],table[:,1],unit='deg')
    match,sep,_=coords.match_to_catalog_sky(pos)
    values=table[match]
    finite=np.isfinite(values[:,2:]).all(axis=1)
    quality=(sep.arcsec<=.7)&finite&(values[:,8]<1.4)&np.all(values[:,[4,5,7]]>0,axis=1)
    radial=np.hypot(sample[:,0]-x,sample[:,1]-y)
    keep=cmd.weights(spec['dm'])[0]
    xy=sample[keep&(radial>=5)&(radial<=11),:2]
    comparison=SkyCoord(*field.sky(*xy.T),unit='deg')
    other,ds,_=comparison.match_to_catalog_sky(pos)
    ids=np.unique(other[ds.arcsec<=.7])
    ref=table[ids]
    ok=(np.isfinite(ref[:,2:]).all(axis=1)&(ref[:,8]<1.4)&np.all(ref[:,[4,5,7]]>0,axis=1))
    ref=ref[ok]
    rng=np.random.default_rng(483327)
    results=[]
    for floor in (.2,.5):
        selected=(p>=floor)
        use=selected&quality
        record=dict(probability_min=floor,ls_sources=int(selected.sum()),gaia_good=int(use.sum()),
                    bright_gaia=int((use&(values[:,9]<20)).sum()))
        if use.any():
            px,pe=values[use,6],values[use,7]
            expected=1000/(10**((spec['dm']+5)/5))
            record.update(expected_parallax_mas=expected,
                          parallax_3sigma_foreground=int(((px-expected)>np.maximum(.15,3*pe)).sum()))
        if use.sum()>=3:
            mean,statistic=motion_statistic(values[use])
            dof=2*(use.sum()-1)
            record.update(mean_pmra_pmdec=mean.tolist(),chi2=statistic,dof=dof,
                          shared_motion_tail=float(chi2.sf(statistic,dof)),
                          **controls(values[use],ref,statistic,rng))
        results.append(record)
    output.parent.mkdir(exist_ok=True,parents=True)
    write_json(output,dict(job=os.getenv('SLURM_JOB_ID'),query=query,service=site,
               input_sha256=sha(cache),raw_gaia_rows=len(table),ls_fixed_TS=fit['ts'],groups=results,control_gaia_cmd_count=len(ref),
               scope='Gaia test of LS-conditioned fixed membership. Shared proper motion tail is '
                     'conditional on the photometric sample, with 0.15 mas/yr variance allowance. '
                     'Control groups match the fitted sample magnitude within 0.6 mag in the '
                     '5–11 arcmin LS CMD annulus. The tail applies only to the now-fixed near mode.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
