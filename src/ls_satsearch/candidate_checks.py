"""Fixed-position sensitivity and independent PS1 source matches for a shortlist."""

import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from astropy.coordinates import SkyCoord
import numpy as np

from .data import select
from .ps1_probe import URL
from .ps1_tiles import COLUMNS, download
from .run import field_cache, read_csv, settings, sha, write_csv, write_json
from .search import CMD, load_isochrone, point_fit


def check(group):
    out = Path('results/holdout')
    field_id = group.split('-')[0]
    modes = [r for r in read_csv(out/'group_review_modes.csv')
             if r['candidate_group_id']==group and r['fit_status']=='complete']
    best = max(modes,key=lambda r:float(r['ts']))
    ra,dec,dm,rh = (float(best[k]) for k in ('fit_ra_deg','fit_dec_deg','fit_dm','fit_rh_arcmin'))
    manifest = json.loads((Path('results/summary')/f'{field_id}-base'/'manifest.json').read_text())
    root,data,cfg = settings()
    field,sources,area,_ = field_cache(root,data,manifest['field'],cfg,None)
    model = load_isochrone(data/'resources'/cfg['isochrone'])
    x,y = field.xy(ra,dec)
    peak = dict(x=x,y=y,dm=dm,rh_arcmin=rh)
    rows, star_positions = [], []
    settings_ = (('base',cfg),('snr7',dict(cfg,min_snr=7)),
                 ('brighter_025',dict(cfg,g_max=cfg['g_max']-.25,r_max=cfg['r_max']-.25)),
                 ('brighter_05',dict(cfg,g_max=cfg['g_max']-.5,r_max=cfg['r_max']-.5)))
    for arm,selection in settings_:
        sample,_,_,_,selected = select(sources,field,area,selection)
        cmd = CMD(sample,model,selection)
        fit,idx,prob = point_fit(sample,cmd,field,area,peak)
        high = prob>=.5
        local = sources[selected][idx[high]]
        rows.append(dict(group_id=group,arm=arm,n_p_ge_half=int(high.sum()),status='fit' if fit else 'unavailable',
                         forced_psf=int(((local['FITBITS']&1)!=0).sum()) if 'FITBITS' in local.dtype.names else None,
                         **(fit or {})))
        if arm=='base':
            star_positions = SkyCoord(local['RA'],local['DEC'],unit='deg')
    write_csv(out/f'{group}-quality_checks.csv',rows)
    work = data/'resources/ps1/v5-shortlist'/group
    work.mkdir(exist_ok=True,parents=True)
    cat = work/'cone.csv'
    url = URL+'.csv?'+urlencode(dict(ra=ra,dec=dec,radius=.05,
                                    primaryDetection=1,columns='['+','.join(COLUMNS)+']',pagesize=25000))
    content = cat.read_bytes() if cat.exists() else download(url)
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    if not reader.fieldnames or not set(COLUMNS)<=set(reader.fieldnames):
        raise ValueError('Unexpected PS1 response columns')
    records = list(reader)
    if len(records)>=25000:
        raise ValueError('The PS1 cone must fit in a single page')
    if not cat.exists():
        cat.write_bytes(content)
    numeric = lambda name: np.array([float(r[name] or 'nan') for r in records])
    common, gr, shape = 0,0,0
    if len(star_positions) and len(records):
        neighbour = SkyCoord(numeric('raStack'),numeric('decStack'),unit='deg')
        ids,sep,_ = star_positions.match_to_catalog_sky(neighbour)
        ids = ids[sep.arcsec<=.8]
        common = len(ids)
        g,r,i,kron = (numeric(k)[ids] for k in ('gPSFMag','rPSFMag','iPSFMag','iKronMag'))
        ge,re,ie = (numeric(k)[ids] for k in ('gPSFMagErr','rPSFMagErr','iPSFMagErr'))
        error = 2.5/np.log(10)/5
        gr_valid = (g>0)&(r>0)&(ge>0)&(ge<=error)&(re>0)&(re<=error)
        point = (i>0)&(kron>0)&(ie>0)&(ie<=error)&(i-kron<.05)
        gr,shape = int(gr_valid.sum()),int((gr_valid&point).sum())
    write_json(out/f'{group}-ps1_source_check.json',dict(group_id=group,job=os.environ.get('SLURM_JOB_ID'),
               ps1_cone_rows=len(records),ra_deg=ra,dec_deg=dec,radius_deg=.05,
               n_ls_p_ge_half=len(star_positions),astro_match_arcsec=.8,n_ps1_match=common,
               n_ps1_gr_snr5=gr,n_ps1_gr_snr5_and_ps1_point=shape,
               input_sha256=sha(cat),catalogue_query=url))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('group')
    check(p.parse_args().group)
