"""Measure the DR11 Bok colour transform against bright public PS1 photometry."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from astropy.coordinates import SkyCoord
import numpy as np

from bass_template import CORRECTION
from ls_satsearch.ps1_probe import URL
from ls_satsearch.ps1_tiles import download
from ls_satsearch.run import field_cache, sha, write_json


def check(path, output):
    root, scratch = (Path(os.environ[k]) for k in ('LS_DR11_ROOT','LS_SAT_DATA'))
    m = json.loads(path.read_text())
    cfg,spec=m['config'],m['field']
    if cfg['region']!='north':
        raise ValueError('This check requires the Bok catalog')
    field, cat, _, _ = field_cache(root,scratch,spec,cfg,None)
    pp = scratch/'resources/v11/ps1'
    pp.mkdir(exist_ok=True,parents=True)
    cache = pp/(spec['id']+'.csv')
    columns = ('objID','raStack','decStack','gPSFMag','rPSFMag','iPSFMag',
               'gPSFMagErr','rPSFMagErr','iPSFMagErr')
    query = URL+'.csv?'+urlencode(dict(ra=spec['ra'],dec=spec['dec'],radius=.22,
              primaryDetection=1,pagesize=25000,columns='['+','.join(columns)+']'))
    if not cache.exists():
        cache.write_bytes(download(query))
    reader = csv.DictReader(io.StringIO(cache.read_text(encoding='utf-8-sig')))
    if not set(columns)<=set(reader.fieldnames or ()):
        raise ValueError('Unexpected PS1 columns')
    rr = {r['objID']:r for r in reader}
    if not 0<len(rr)<25000:
        raise ValueError('Incomplete PS1 cone')
    ps = np.array([[float(row[k] or 'nan') for k in columns[1:]] for row in rr.values()])
    keep = np.isfinite(ps).all(axis=1)&(ps[:,2]>16.5)&(ps[:,2]<21)&(ps[:,3:5]>0).all(axis=1)
    keep &= ((ps[:,5:]>0)&(ps[:,5:]<.045)).all(axis=1)
    ps = ps[keep]
    center = SkyCoord(field.ra, field.dec, unit='deg')
    ast = SkyCoord(cat['RA'],cat['DEC'],unit='deg')
    use = (ast.separation(center).deg<.225)&(np.char.strip(cat['TYPE'].astype('U'))=='PSF')
    for band in 'GR':
        use &= (cat[f'FLUX_{band}']>0)&(cat[f'FLUX_IVAR_{band}']>0)
    cat,ast = cat[use],ast[use]
    ps_sky = SkyCoord(ps[:,0],ps[:,1],unit='deg')
    index,sep,_=ps_sky.match_to_catalog_sky(ast)
    color = ps[:,2]-ps[:,4]
    keep = (sep.arcsec<.75)&(color>=.4)&(color<=2.7)
    _, unique = np.unique(index[keep],return_index=True)
    psidx = np.flatnonzero(keep)[unique]
    bok = cat[index[psidx]]
    if len(bok)<25:
        raise ValueError('Too few unique bright calibration matches')
    stats={}
    for k,(b,c) in enumerate(CORRECTION.items(),2):
        flux=bok[f'FLUX_{b.upper()}']
        obs=22.5-2.5*np.log10(flux)
        delta=obs-ps[psidx,k]
        resid=delta-np.polynomial.polynomial.polyval(color[psidx],c)
        stats[b]=dict(raw_bok_minus_ps1_p16_p50_p84=np.percentile(delta,[16,50,84]).tolist(),
                      corrected_p16_p50_p84=np.percentile(resid,[16,50,84]).tolist())
    write_json(output,dict(field=spec['id'],job=os.getenv('SLURM_JOB_ID'),
             public_query=query,ps1_sha256=sha(cache),matches=len(bok),bands=stats))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    check(a.manifest,a.output)
