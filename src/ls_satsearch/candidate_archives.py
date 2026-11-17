"""Bounded Gaia, DESI and CADC queries around the frozen candidate."""

import csv
import io
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy_healpix import HEALPix
import fitsio
import numpy as np
from scipy.stats import chi2

from .run import sha, write_json
from .verify_candidate import OUT, setup


GAIA = 'https://gea.esac.esa.int/tap-server/tap/sync'
GAIA_MIRROR = 'https://gaia.ari.uni-heidelberg.de/tap/sync'
CADC = 'https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync'
DESI = Path('/global/cfs/cdirs/desi/public/dr2/spectro/redux/loa/healpix')


def tap(endpoint, query, columns, path, method='POST'):
    args=urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))
    url=endpoint+'?'+args if method=='GET' else endpoint
    if path.exists():
        payload=path.read_bytes()
    else:
        with urlopen(url, data=None if method=='GET' else args.encode(), timeout=35) as req:
            payload=req.read()
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if not reader.fieldnames or not set(columns)<=set(reader.fieldnames):
        raise ValueError('Missing expected archive columns')
    rows=list(reader)
    path.write_bytes(payload)
    return rows


def gaia(pos, center, cache):
    columns=('source_id','ra','dec','parallax','parallax_error','pmra','pmra_error',
             'pmdec','pmdec_error','pmra_pmdec_corr','ruwe','phot_g_mean_mag','radial_velocity')
    cone=f'CIRCLE({center.ra.deg},{center.dec.deg},0.04)'
    query=f"SELECT TOP 5000 {','.join(columns)} FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT(ra,dec),{cone})"
    path=cache/'gaia-astrometry.csv'
    errors=[]
    for endpoint in (GAIA,GAIA_MIRROR):
        try:
            rows=tap(endpoint,query,columns,path,'GET')
            break
        except (ValueError,OSError) as e:
            errors.append(f'{endpoint}: {e}')
    else:
        return dict(status='unavailable',errors=errors)
    if len(rows)>=5000:
        raise ValueError('Gaia cone truncated')
    positions=SkyCoord([float(r['ra']) for r in rows],[float(r['dec']) for r in rows],unit='deg')
    matches=[]
    if rows:
        idx,sep,_=pos.match_to_catalog_sky(positions)
        matches=[rows[i] for i in idx[sep.arcsec<=.8]]
    qualified=[r for r in matches if r['ruwe'] and float(r['ruwe'])<1.4 and r['parallax_error']
               and float(r['parallax_error'])>0]
    foreground=[r for r in qualified if float(r['parallax'])>max(.15,3*float(r['parallax_error']))]
    result=dict(status='complete',endpoint=endpoint,gaia_cone_sources=len(rows),matches=len(matches),
                qualified_parallax=len(qualified),foreground_parallax=len(foreground),
                astrometric_matches_with_pm=sum(bool(r['pmra'] and r['pmdec']) for r in matches),
                radial_velocity_matches=sum(bool(r['radial_velocity']) for r in matches),
                match_arcsec=.8,input_sha256=sha(path))
    inputs=('pmra','pmdec','pmra_error','pmdec_error','pmra_pmdec_corr')
    others=[r for r in qualified if r not in foreground and all(r[k] for k in inputs)]
    if len(others)==2:
        p1,p2=[[float(r[k]) for k in inputs] for r in others]
        diff=np.array(p1[:2])-p2[:2]
        cov=np.zeros((2,2))
        for _,_,a,b,rho in (p1,p2):
            cov+=np.array([[a*a,rho*a*b],[rho*a*b,b*b]])
        q=float(diff@np.linalg.solve(cov,diff))
        result.update(pm_pair_n=2,pm_consistency_chi2=q,pm_consistency_tail=float(chi2.sf(q,2)))
    return result


def desi(pos,center,veto_output=None):
    pixels=HEALPix(nside=64,order='nested',frame='icrs').cone_search_skycoord(center,.04*u.deg)
    files=[]
    targets=set()
    near=set()
    solutions={}
    coordinates={}
    for pix in pixels:
        for p in DESI.glob(f'*/*/{pix//100}/{pix}/redrock-*.fits'):
            f=fitsio.read(p,ext='FIBERMAP',columns=['TARGETID','TARGET_RA','TARGET_DEC'])
            usable=np.isfinite(f['TARGET_RA']+f['TARGET_DEC'])&(abs(f['TARGET_DEC'])<=90)
            sky=SkyCoord(f['TARGET_RA'][usable],f['TARGET_DEC'][usable],unit='deg')
            if len(sky):
                ids,sep,_=pos.match_to_catalog_sky(sky)
                matched=set(int(x) for x in f['TARGETID'][usable][ids[sep.arcsec<=.8]])
                targets.update(matched)
                if veto_output is not None and matched:
                    for ident,j in zip(f['TARGETID'][usable][ids[sep.arcsec<=.8]],ids[sep.arcsec<=.8]):
                        coordinates[int(ident)]=dict(ra=float(sky[j].ra.deg),dec=float(sky[j].dec.deg))
                    estimates=fitsio.read(p,ext='REDSHIFTS',
                                          columns=['TARGETID','SPECTYPE','Z','ZERR','ZWARN','DELTACHI2'])
                    for row in estimates[np.isin(estimates['TARGETID'],list(matched))]:
                        kind=row['SPECTYPE']
                        if isinstance(kind,bytes):
                            kind=kind.decode()
                        solutions.setdefault(int(row['TARGETID']),[]).append(dict(
                            program=p.parent.parent.parent.name,spectral_class=kind.strip(),
                            redshift=float(row['Z']),redshift_error=float(row['ZERR']),
                            zwarn=int(row['ZWARN']),delta_chi2=float(row['DELTACHI2'])))
                near.update(int(x) for x in f['TARGETID'][usable][sky.separation(center).arcmin<=2.4])
            files.append(str(p))
    result=dict(status='complete',release='DESI DR2 loa',healpix=pixels.tolist(),files_scanned=len(files),
                files=files,cone_spectroscopic_targets=len(near),member_matches=len(targets),match_arcsec=.8)
    if veto_output is not None:
        result['matched_redrock_solutions']=list(solutions.values())
        checks=[coordinates[i] for i,records in solutions.items()
                if records and all(r['spectral_class']=='QSO' and r['zwarn']==0 for r in records)]
        write_json(veto_output, checks)
        result['qso_veto_count']=len(checks)
    return result


def frozen_positions(plan,data,sources):
    with np.load(data/'runs'/plan.get('scratch_revision','v5')/f"{plan['field']}-base"/f"membership-main-A-{plan['membership_rank']}.npz",
                 allow_pickle=False) as h:
        ids={tuple(r) for r in h['source_ids'][h['probability']>=.5]}
    qa=np.isin(sources['BRICKID'],[i[1] for i in ids])&np.isin(sources['OBJID'],[i[2] for i in ids])
    raw=sources[qa]
    chosen=np.array([tuple(r) in ids for r in raw[['RELEASE','BRICKID','OBJID']]])
    raw=raw[chosen]
    if len(raw)!=len(ids) or not len(raw):
        raise ValueError('Could not map frozen LS member identifiers uniquely')
    return SkyCoord(raw['RA'],raw['DEC'],unit='deg')


def run():
    plan,_,data,_,sources,_=setup()
    cache=data/'resources/v6'/plan['candidate']
    cache.mkdir(exist_ok=True,parents=True)
    OUT.mkdir(exist_ok=True,parents=True)
    pos=frozen_positions(plan,data,sources)
    center=SkyCoord(plan['ra_deg'],plan['dec_deg'],unit='deg')
    write_json(OUT/'astrometry_and_spectroscopy.json',dict(job=os.environ.get('SLURM_JOB_ID'),
               frozen_ls_candidates=len(pos),gaia=gaia(pos,center,cache),desi=desi(pos,center)))


if __name__=='__main__':
    run()
