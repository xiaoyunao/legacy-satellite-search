"""Fixed-position diagnostics for four misses in the frozen DR11 A search."""
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import shapely

from ls_satsearch.data import select
from ls_satsearch.run import field_cache, read_csv, sha, write_csv, write_json
from ls_satsearch.search import CMD, binomial_tail_score, exact_onoff, load_isochrone
from scripts.v14_mask_tiles import cache_key

MASK=Path('results/v14/production_integration/masks')
OUT=Path('results/v14/census_comparison')
NAMES={'Gemini_I_DELVE_8','DELVE_7','Aquarius_IV','Sextans_II'}


def covering(reg,rows,ra,dec):
    y=math.sin(math.radians(dec))
    point=shapely.Point(ra,y)
    for entry in rows:
        if entry['classification']!='qualified_discovery':
            continue
        for label,bounds in enumerate(entry['bounds']):
            if not bounds or not(bounds[0]<=ra<=bounds[2] and bounds[1]<=y<=bounds[3]):
                continue
            path=Path(reg['cache'])/f"{entry['cache_key']}-{label}.wkb"
            if sha(path)!=entry['geometry_sha256'][path.name]:
                raise ValueError('Accepted WCS polygon changed')
            if shapely.from_wkb(path.read_bytes()).covers(point):
                yield entry['cache_key']
                break


def diagnose(truth,record,inputs,cutoffs):
    root,data=(Path(os.environ[k]) for k in ('LS_DR11_ROOT','LS_SAT_DATA'))
    path=Path(record['manifest'])
    if sha(path)!=record['manifest_sha256']:
        raise ValueError('Original field scan changed')
    inputs[str(path)]=sha(path)
    scan=json.loads(path.read_text())
    cfg=scan['config']
    template=data/'resources'/cfg['isochrone']
    if sha(template)!=scan['model_sha256']:
        raise ValueError('Original template changed')
    field,raw,area,_=field_cache(root,data,scan['field'],cfg,None)
    ra,dec=float(truth['ra_deg']),float(truth['dec_deg'])
    x,y=field.xy(ra,dec)
    lx,ly=field.xy(raw['RA'],raw['DEC'])
    rr=np.hypot(lx-x,ly-y)
    true_rh=float(truth['theta_h_arcmin'])
    raw=raw[rr<=6*max(max(cfg['radii_arcmin']),true_rh)]
    rr=rr[rr<=6*max(max(cfg['radii_arcmin']),true_rh)]
    mu=5*math.log10(float(truth['D_kpc']))+10
    lo,hi,step=cfg['dm']
    distances=np.arange(lo,hi+step/2,step)
    nearest=float(distances[np.argmin(abs(distances-mu))])
    locus=load_isochrone(template)[2]
    rows=[]
    for arm,arm_cfg in (('baseline',cfg),('deeper_diagnostic',dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5))):
        sample,_,valid,mags,chosen=select(raw,field,area,arm_cfg)
        tree=cKDTree(sample[:,:2])
        any_gr=np.flatnonzero(valid)
        err=np.column_stack([2.5/np.log(10)/(raw[f'FLUX_{b}'][valid]*np.sqrt(raw[f'FLUX_IVAR_{b}'][valid])) for b in 'GR'])
        for dm_role,dm in (('literature',mu),('nearest_grid',nearest)):
            selected=CMD.top_hat(sample[:,2:4],sample[:,4:6],dm,locus)
            all_cmd=CMD.top_hat(mags[valid],err,dm,locus)
            for rh in sorted(set([true_rh,*cfg['radii_arcmin']])):
                n_on,n_off,a_on,a_off=exact_onoff(field,x,y,rh,tree,area,selected)
                core=rr<=1.5*rh
                _,flow,_,_,_=select(raw[core],field,area,arm_cfg)
                n_extended=int((core[any_gr]&all_cmd&~chosen[any_gr]).sum())
                fractions=[a_on/(math.pi*(1.5*rh)**2),a_off/(math.pi*(6**2-3.5**2)*rh**2)]
                enough=fractions[0]>=cfg['min_on_fraction'] and fractions[1]>=cfg['min_off_fraction']
                expected=n_off*a_on/a_off if a_off else None
                rows.append(dict(name=truth['name'],field=record['field'],region=record['region'],
                    arm=arm,dm_role=dm_role,dm=dm,rh_arcmin=rh,
                    formal_grid_scale=rh in cfg['radii_arcmin'],raw=flow['raw'],valid_g=flow['valid_G'],
                    gr_snr=flow['snr_R'],mag_gr=flow['mag_R'],gr_usable=flow['area'],psf=flow['psf'],
                    cmd_psf_on=n_on,cmd_non_psf_on=n_extended,cmd_psf_off=n_off,area_on=a_on,area_off=a_off,
                    on_fraction=fractions[0],off_fraction=fractions[1],mask_eligible=enough,
                    background_expected_on=expected,
                    fixed_centre_score=binomial_tail_score(n_on,n_on+n_off,a_on/(a_on+a_off)) if enough else None,
                    baseline_cut_from_existing_records='|'.join(sorted(cutoffs.get(record['field'],set()))),
                    forced_position=True,ordinary_blind_recovery=False))
    return rows


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Run with allocated NERSC CPU')
    receipt=MASK/'post_outside_C_registration_20261120.json'
    bind=json.loads(receipt.read_text())
    reg_path=Path(bind['registration'])
    if sha(reg_path)!=bind['registration_sha256']:
        raise ValueError('Production mask registration changed')
    reg=json.loads(reg_path.read_text())
    index=Path(reg['output'])/'vector_index.json'
    tile=json.loads((index.parent/'overlay_repair_registration.json').read_text())
    if tile['vector_index_sha256']!=sha(index):
        raise ValueError('Frozen geometry index changed')
    rows=json.loads(index.read_text())['records']
    fields={cache_key(r,reg):r for r in reg['records']}
    source=Path('references/benchmarks.csv')
    ledger=OUT.parent/'production_integration/reconciled/qualified_discovery_records.csv'
    cutoffs={}
    for r in read_csv(ledger):
        cutoffs.setdefault(r['field'],set()).add(r['cutoff'])
    inputs={str(p):sha(p) for p in (receipt,reg_path,index,source,ledger)}
    results=[]
    for truth in read_csv(source):
        if truth['name'] not in NAMES:
            continue
        matches=list(covering(reg,rows,float(truth['ra_deg']),float(truth['dec_deg'])))
        if not matches:
            raise ValueError('Lost registered target coverage')
        for key in matches:
            results.extend(diagnose(truth,fields[key],inputs,cutoffs))
        print(dict(target=truth['name'],covering_original_fields=len(matches)),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/'missed_controls_fixed_diagnostics.csv',results)
    write_json(OUT/'missed_controls_manifest.json',dict(job=os.environ['SLURM_JOB_ID'],
        inputs=inputs,code_sha256=sha(Path(__file__)),rows=len(results),
        scope='Fixed-centre diagnostics. Counts follow each eligible original field and its actual mask. Deeper offsets reuse the same catalogue and mask. Nominal binomial scores are descriptive; no discovery, membership or blind recall claims.'))


if __name__=='__main__':
    main()
