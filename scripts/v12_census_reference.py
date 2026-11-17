"""Query the published PS1 DR1 model at the exact round 12 injection centres."""

import argparse
import os
from pathlib import Path

import numpy as np
import xgboost as xgb
import yaml

from ls_satsearch.census_reference import map_at
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run(inputs, output):
    data=Path(os.environ['LS_SAT_DATA'])
    resources=data/'resources/v9/census'
    model=resources/'classifier_stellar_ps1_v13.0.1.model'
    density_path=resources/'ps1_stellar_density_r22_equ_n128_v0.fits'
    mask_path=data/'resources/ps1/ps1d_mask_v2.1.fits'
    bits=yaml.safe_load((resources/'read_config.yaml').read_text())['maskbits']
    bad=sum(bits[k] for k in ('ASSOC','STAR','EBV','DENSITY','FOOT'))
    rows=[r for p in inputs for r in read_csv(p) if r['survey']=='ps1']
    if not rows:
        raise ValueError('No PS1 comparison trials')
    ra,dec,distance,radius,luminosity=np.array([[float(r[k]) for k in
        ('truth_ra_deg','truth_dec_deg','D_kpc','rh_pc','expected_MV_proxy')] for r in rows]).T
    density=map_at(density_path,ra,dec)
    mask=map_at(mask_path,ra,dec)
    eligible=((mask&bad)==0)&np.isfinite(density)&(density>=0)
    actual_lum=np.array([float(r['actual_MV_proxy']) if r['actual_MV_proxy'] else np.nan for r in rows])
    booster=xgb.Booster(params={'nthread':1})
    booster.load_model(model)
    def evaluate(light):
        good=eligible&np.isfinite(light)
        x=np.column_stack([np.log10(distance[good]),light[good],np.log10(radius[good]/1000),density[good]])
        pred=np.full(len(rows),np.nan)
        if good.any():
            pred[good]=booster.predict(xgb.DMatrix(x))
            if not np.all((0<=pred[good])&(pred[good]<=1)):
                raise ValueError('Calibrated classifier output outside probability range')
        return pred
    expected,actual=evaluate(luminosity),evaluate(actual_lum)
    output.mkdir(exist_ok=True,parents=True)
    write_csv(output/'published_ps1_dr1_reference.csv',[
        dict({k:r[k] for k in ('field','region','trial','D_kpc','rh_pc','expected_MV_proxy','actual_MV_proxy')},
             stellar_density_r22=density[i], eligible=eligible[i], compact_outside_population_sample=radius[i]<15,
             reference_at_expected_proxy=expected[i] if eligible[i] else None,
             reference_at_actual_proxy=actual[i] if np.isfinite(actual[i]) else None)
        for i,r in enumerate(rows)])
    write_json(output/'published_ps1_dr1_reference.json',dict(job=os.environ.get('SLURM_JOB_ID'),
               source_commit='1a02f50d25cac74c02ddba8401a5af20aa2db4fe',model_sha256=sha(model),
               density_sha256=sha(density_path),mask_sha256=sha(mask_path),xgboost=xgb.__version__,
               scope='Published PS1 DR1 thresholds only. Survey predictions use requested/realized V proxy; '
                     'they have no matched-review-cost interpretation relative to internal PS1 DR2.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('inputs',nargs='+',type=Path)
    a=p.parse_args()
    run(a.inputs,a.output)
