"""Test Gaia astrometry of a frozen LS shortlist without fitting a selected subset."""
import argparse
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np
from scipy.stats import chi2
import yaml

from .candidate_archives import GAIA, GAIA_MIRROR, desi, frozen_positions, tap
from .compare_candidate_gaia import coords, known_foreground
from .run import sha, write_json
from .verify_candidate import setup


def common_motion(rows):
    values, cov = [], []
    for r in rows:
        if not all(r[k] for k in ('pmra','pmdec','pmra_error','pmdec_error','pmra_pmdec_corr')):
            continue
        a,b,c = map(float,[r['pmra_error'],r['pmdec_error'],r['pmra_pmdec_corr']])
        if a<=0 or b<=0 or abs(c)>=1:
            continue
        cov.append([[a*a,c*a*b],[c*a*b,b*b]])
        values.append([float(r['pmra']),float(r['pmdec'])])
    n=len(values)
    if n<2:
        return dict(n=n)
    inv=np.linalg.inv(np.asarray(cov))
    model_cov=np.linalg.inv(inv.sum(axis=0))
    mean=model_cov@np.einsum('nij,nj->i',inv,values)
    resid=values-mean
    q=float(np.einsum('ni,nij,nj->',resid,inv,resid))
    return dict(n=n,mean_masyr=mean.tolist(),covariance=model_cov.tolist(),
                chi2=q,dof=2*n-2,tail=float(chi2.sf(q,2*n-2)))


def run(policy):
    rule=yaml.safe_load(policy.read_text())
    plan,_,data,_,sources,_=setup(Path(rule['followup']))
    pos=frozen_positions(plan,data,sources)
    center=SkyCoord(plan['ra_deg'],plan['dec_deg'],unit='deg')
    cache=data/'resources'/plan['scratch_revision']/plan['candidate']
    path=cache/'gaia-astrometry.csv'
    columns=('source_id','ra','dec','parallax','parallax_error','pmra','pmra_error',
             'pmdec','pmdec_error','pmra_pmdec_corr','ruwe','phot_g_mean_mag','radial_velocity')
    query=f"SELECT TOP 5000 {','.join(columns)} FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT(ra,dec),CIRCLE({center.ra.deg},{center.dec.deg},0.04))"
    try:
        rows=tap(GAIA,query,columns,path,'GET')
        endpoint=GAIA
    except (ValueError,OSError):
        rows=tap(GAIA_MIRROR,query,columns,path,'GET')
        endpoint=GAIA_MIRROR
    if len(rows)>=5000:
        raise ValueError('Gaia result is truncated')
    matches=[]
    if rows:
        idx,sep,_=pos.match_to_catalog_sky(coords(rows))
        matches=[rows[i] for i in sorted(set(idx[sep.arcsec<=rule['gaia_match_arcsec']]))]
    qualified, foreground=known_foreground(matches,rule)
    selected=[r for r in qualified if r not in foreground]
    distances=[]
    for dm in rule['fixed_dm']:
        expected=10**(2-dm/5)
        for zp in rule['gaia_parallax_zero_point_mas']:
            pulls=[(float(r['parallax'])-zp-expected)/np.hypot(float(r['parallax_error']),
                   rule['gaia_parallax_floor_mas']) for r in selected]
            distances.append(dict(dm=dm,expected_mas=expected,zero_point_sensitivity_mas=zp,
                n=len(pulls),within_3sigma=int((np.abs(pulls)<=3).sum()),chi2=float(np.square(pulls).sum())))
    out=Path(rule.get('output','results/v8/survey14'))
    out.mkdir(exist_ok=True,parents=True)
    write_json(out/'astrometry.json',dict(job=os.environ.get('SLURM_JOB_ID'),endpoint=endpoint,
        input_sha256=sha(path),shortlist=len(pos),cone_rows=len(rows),matched=len(matches),
        qualified=len(qualified),foreground=len(foreground),common_motion=common_motion(selected),
        all_qualified_motion=common_motion(qualified),
        radial_velocities=sum(bool(r['radial_velocity']) for r in selected),distances=distances,
        desi=desi(pos,center,veto_output=cache/'desi-qso-veto.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path,default=Path('configs/v8/survey14.yaml'))
    run(parser.parse_args().policy)
