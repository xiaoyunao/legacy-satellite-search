"""Test frozen stellar-population hypotheses using independent PS1 and BASS data."""
import argparse
import json
import os
from pathlib import Path
import re

import fitsio
import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import select, sample_pixels, Field, load_bricks, make_area, sweeps
from ls_satsearch.run import field_cache, sha, write_csv, write_json
from ls_satsearch.search import CMD, exact_onoff, load_isochrone, point_fit, scan
from ls_satsearch import verify_candidate

PLAN=Path('configs/v14/0706/followup.yaml')
OUTPUT=Path('results/v14/0706')


def exposures():
    root=Path(os.environ['LS_DR11_ROOT'])
    plan=yaml.safe_load(PLAN.read_text())
    a,d=plan['ra_deg'],plan['dec_deg']
    field=Field(a,d,.12,.1666667,buffer=0)
    own={}
    for region in ('south','north'):
        bricks=load_bricks(root,region)
        inside=field.overlap(bricks['RA1'],bricks['RA2'],bricks['DEC1'],bricks['DEC2'])
        stored=set()
        for row in bricks[inside]:
            name=row['BRICKNAME'].strip()
            path=root/region/'coadd'/name[:3]/name/f'legacysurvey-{name}-ccds.fits'
            if not path.exists():
                continue
            src=fitsio.read(path,columns=['camera','expnum','filter'],upper=True)
            stored.update((str(r['CAMERA']).strip(),int(r['EXPNUM']),str(r['FILTER']).strip()) for r in src)
        own[region]=stored
    archive=json.loads((OUTPUT/'archive_audit.json').read_text())
    records={}
    for row in archive['archives']['NOIRLab']['rows']:
        original=row.get('original_filename','')
        exp=re.search(r'DECam_(\d+)',original)
        if exp is None or row['proc_type']!='instcal' or row['prod_type']!='image':
            continue
        n=int(exp[1]);band=row['filter'].split()[0]
        key=n,band
        records[key]=dict(row,expnum=n,band=band,
             used_in_south=any(e==n and b==band and c=='decam' for c,e,b in own['south']))
    write_csv(OUTPUT/'noirlab_independence.csv',list(records.values()))
    write_json(OUTPUT/'noirlab_independence.json',dict(job=os.getenv('SLURM_JOB_ID'),
               primary_test_box_deg=.12,north_inputs=len(own['north']),south_inputs=len(own['south']),
               independent_decam_visits=sum(not r['used_in_south'] for r in records.values())))


def bass():
    root=Path(os.environ['LS_DR11_ROOT']);data=Path(os.environ['LS_SAT_DATA'])
    plan=yaml.safe_load(PLAN.read_text())
    cfg=yaml.safe_load(Path('configs/v12/cohorts/north/search.yaml').read_text())
    cfg['regional_primary']=False
    cfg.update(radii_arcmin=[.5,1,2],dm=[13.5,22.5,.25])
    field=Field(plan['ra_deg'],plan['dec_deg'],.26,1/6,buffer=20)
    raw,inputs=sweeps(root,field,'north')
    area,metadata=make_area(root,field,load_bricks(root,'north'),sum(1<<i for i in cfg['reject_maskbits']),2,region='north')
    sample,cutflow,*_=select(raw,field,area,cfg)
    model=load_isochrone(data/'resources'/cfg['isochrone'])
    cmd=CMD(sample,model,cfg)
    center=np.array(field.xy(plan['ra_deg'],plan['dec_deg']))
    rows=[]
    for dm in np.arange(13.5,22.51,.25):
        accepted,ratio=cmd.weights(dm)
        on,off,area_on,area_off=exact_onoff(field,*center,.5,cKDTree(sample[:,:2]),area,accepted)
        peak=dict(x=center[0],y=center[1],dm=dm,rh_arcmin=.5)
        fit,ids,prob=point_fit(sample,cmd,field,area,peak,ratio=ratio)
        if fit:
            valid=np.ones(len(sample),dtype=bool);valid[ids[np.argsort(prob)[-3:]]]=False
            reduced,*_=point_fit(sample[valid],cmd,field,area,peak,ratio=ratio[valid])
        else:
            reduced=None
        rows.append(dict(dm=float(dm),on=on,off=off,area_on=area_on,area_off=area_off,
                         C_TS=fit['ts'] if fit else None,C_TS_after3=reduced['ts'] if reduced else None))
    _,peaks,_,_=scan(sample,field,area,model,cfg)
    near=[dict(dm=p['dm'],rh_arcmin=p['rh_arcmin'],score=p['score'],
               offset_arcmin=float(np.hypot(p['x'],p['y']))) for p in peaks
          if np.hypot(p['x'],p['y'])<=2]
    write_csv(OUTPUT/'bass_fixed_population.csv',rows)
    write_csv(OUTPUT/'bass_blind_nearby.csv',near)
    fixed=next(r for r in rows if r['dm']==plan['dm'])
    write_json(OUTPUT/'bass_summary.json',dict(job=os.getenv('SLURM_JOB_ID'),selected=len(sample),
                 fixed=fixed,inputs=inputs,coverage=metadata,cutflow=cutflow,
                 notes='Independent BASS exposures, BASS template. Fixed-centre and local blind diagnostics.'))


if __name__=='__main__':
    OUTPUT.mkdir(exist_ok=True,parents=True)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ps1-fixed',action='store_true')
    args=parser.parse_args()
    verify_candidate.OUT=OUTPUT/'ps1'
    verify_candidate.OUT.mkdir(exist_ok=True)
    if args.ps1_fixed:
        verify_candidate.run(policy=PLAN)
    else:
        exposures()
        bass()
        verify_candidate.run(local_review=True,policy=PLAN)
