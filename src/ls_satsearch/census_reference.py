"""Evaluate the released PS1 DR1 census model at the frozen pilot sites."""

from pathlib import Path
from importlib.metadata import version
import os

from astropy.io import fits
import astropy.units as u
from astropy_healpix import HEALPix
import numpy as np
import yaml

from .inject import choose_sites
from .ps1_tiles import design
from .run import config_path, settings, sha, write_csv, write_json


def map_at(path, ra, dec):
    with fits.open(path,memmap=True) as hdus:
        hdu=hdus[1]
        header=hdu.header
        if header['ORDERING'].strip()!='RING' or header['INDXSCHM'].strip()!='IMPLICIT':
            raise ValueError(f'Unsupported survey map layout: {path}')
        pix=HEALPix(nside=header['NSIDE'],order='ring').lonlat_to_healpix(ra*u.deg,dec*u.deg)
        return np.asarray(hdu.data.field(0).reshape(-1)[pix])


def run():
    import xgboost as xgb

    _,data,cfg=settings()
    resources=data/'resources/v9/census'
    model=resources/'classifier_stellar_ps1_v13.0.1.model'
    density_path=resources/'ps1_stellar_density_r22_equ_n128_v0.fits'
    mask_path=data/'resources/ps1/ps1d_mask_v2.1.fits'
    bits=yaml.safe_load((resources/'read_config.yaml').read_text())['maskbits']
    bad=sum(bits[k] for k in ('ASSOC','STAR','EBV','DENSITY','FOOT'))
    booster=xgb.Booster(params={'nthread':1})
    booster.load_model(model)
    matched=yaml.safe_load(config_path('matched.yaml').read_text())
    plan=yaml.safe_load(Path('configs/v9/physical_trials.yaml').read_text())
    distance,radius,luminosity=np.array(plan['conditions'],dtype=float).T
    rows=[]
    for spec in matched['fields']:
        field_id=spec['id']
        if field_id not in ('fresh_05','fresh_09'):
            continue
        field,_=design(spec,matched)
        area=np.load(data/'runs/v4/matched/ps1'/field_id/'coverage.npy',allow_pickle=False)
        rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],int(spec['ra']*1000),plan['seed']]))
        sites=np.asarray(choose_sites(field,area,cfg,len(distance),rng))
        ra,dec=field.sky(*sites.T)
        density=map_at(density_path,ra,dec)
        mask=map_at(mask_path,ra,dec)
        inputs=np.column_stack([np.log10(distance),luminosity,np.log10(radius/1000),density])
        if not np.all(np.isfinite(inputs)) or (density<0).any():
            raise ValueError('Invalid stellar density at comparison site')
        prediction=booster.predict(xgb.DMatrix(inputs))
        if not np.all((0<=prediction)&(prediction<=1)):
            raise ValueError('Unexpected census model output')
        eligible=(mask&bad)==0
        for i,p in enumerate(np.where(eligible,prediction,0)):
            rows.append(dict(field=field_id,trial=i,D_kpc=distance[i],rh_pc=radius[i],
                             requested_MV=luminosity[i],stellar_density_r22=density[i],
                             eligible=bool(eligible[i]),pdet_census_ps1_dr1=float(p),
                             compact_outside_population_sample=bool(radius[i]<15)))
    out=Path('results/v9/physical_trials')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'published_ps1_dr1_reference.csv',rows)
    write_json(out/'published_ps1_dr1_reference.json',dict(job=os.environ.get('SLURM_JOB_ID'),
                 xgboost=version('xgboost-cpu'),model_sha256=sha(model),density_sha256=sha(density_path),
                 mask_sha256=sha(mask_path),source_commit='1a02f50d25cac74c02ddba8401a5af20aa2db4fe',
                 fields=['fresh_05','fresh_09'],scope='Published PS1 DR1 thresholds and simulations; compare separately from matched internal peak budget'))


if __name__=='__main__':
    run()
