"""Replay frozen populations without modifying truth; audit truncation and PS1 support."""
import json
import os
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv, settings, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone
from scripts.v13_image_trials import context, local_coordinates, template_paths


def replay(plan, number, model, decam):
    distance, rh, mv = plan['conditions'][number]
    rng = np.random.default_rng([plan['seed'], number])
    center = rng.uniform(-.40, .40, size=2)
    proxy = 10**(-.4*(decam[0][:,0]-.59*(decam[0][:,0]-decam[0][:,1])-.01))
    total = 10**(-.4*mv)/(decam[1]@proxy)
    draw = rng.poisson(total*model[1])
    valid = np.any(np.column_stack([model[0],decam[0]]) < np.array([26,25.5]*2)-20,axis=1)
    indices = np.repeat(np.arange(len(draw)),draw*valid)
    q = rng.random(len(indices)); angle = rng.uniform(0,2*np.pi,len(indices))
    arc = np.rad2deg(np.arctan(rh/(1000*distance)))*60
    xy = center+(arc*np.sqrt(q/(1-q)))[:,None]*np.column_stack([np.cos(angle),np.sin(angle)])
    retain = np.linalg.norm(xy,axis=1)<plan['splice_radius_arcmin']-.03
    return indices, xy, retain, draw, proxy, center


def support_bin(g, color, rows):
    for row in rows:
        lo=float(row['ls_color_lo']) if row['ls_color_lo'] else -np.inf
        hi=float(row['ls_color_hi']) if row['ls_color_hi'] else np.inf
        if float(row['ls_g_lo'])<=g<float(row['ls_g_hi']) and lo<=color<hi:
            return int(row['references'])>=20
    return False


def run():
    _,data,_=settings()
    out=Path('results/v14/repeat_full/population_audit');out.mkdir(parents=True,exist_ok=True)
    response=Path('results/v14/repeat/ps1_response/selection_stage_counts.csv')
    training=read_csv(response);rows=[];sources={str(response):sha(response)}
    for site in read_csv(Path('configs/v14_repeat/image_fields.csv')):
        name=site['field'];_,plan,cfg=context(name)
        native,decam_path=template_paths(data,cfg)
        model=load_isochrone(native);decam=load_isochrone(decam_path)
        training_site=[r for r in training if r['site']==name and r['split']=='train']
        field=local_coordinates(site)
        for trial,cell in enumerate(plan['conditions']):
            folder=data/'image-v14_repeat'/name/f'trial{trial:02d}'
            truth=np.load(folder/'truth.npy',allow_pickle=False)
            meta=json.loads((folder/'truth.json').read_text())
            indices,xy,keep,draw,proxy,center=replay(plan,trial,model,decam)
            dm=5*np.log10(cell[0])+10
            if not np.array_equal(truth['g0'],model[0][indices[keep],0]+dm):
                raise ValueError('Replayed population differs from prepared truth')
            if not np.allclose(np.column_stack(field.xy(truth['ra'],truth['dec'])),xy[keep],atol=1e-7,rtol=0):
                raise ValueError('Replayed positions differ from prepared truth')
            light=float(draw@proxy)
            if int(draw.sum())!=meta['N_imf'] or not np.isclose(-2.5*np.log10(light),meta['realized_MV_proxy']):
                raise ValueError('Replayed integrated light differs from registration')
            # This is a support audit only, not a truth-level PS1 probability.
            use=truth['g0']<24.5
            supported=sum(support_bin(g,g-r,training_site) for g,r in zip(truth['g0'][use],truth['r0'][use]))
            sources[str(folder/'truth.npy')]=sha(folder/'truth.npy')
            rows.append(dict(site=name,trial=trial,latent_population_id=trial,realization_id=trial//6,
                D_kpc=cell[0],rh_pc=cell[1],target_MV_proxy=cell[2],realized_MV_proxy=meta['realized_MV_proxy'],
                N_imf=int(draw.sum()),N_magnitude_eligible_before_stamp=len(indices),N_rendered=int(keep.sum()),
                N_lost_at_stamp=int((~keep).sum()),fraction_retained_potential=float(keep.mean()),
                eligible_light_before_stamp=float(proxy[indices].sum()),
                eligible_light_after_stamp=float(proxy[indices[keep]].sum()),full_IMF_light_proxy=light,
                center_x_arcmin=center[0],center_y_arcmin=center[1],
                N_rendered_g0_lt24p5=int(use.sum()),N_proxy_supported_g0_lt24p5=supported,
                truncation_recovery_sensitivity='not_measured_by_replay'))
    write_csv(out/'population_stamp_and_support.csv',rows)
    cells=[]
    for rh in (3,10,30):
        for mv in (-3,-1.5):
            sample=[r for r in rows if r['site']=='v14_south_response_1' and r['rh_pc']==rh and r['target_MV_proxy']==mv]
            values=[r['realized_MV_proxy'] for r in sample]
            cells.append(dict(rh_pc=rh,target_MV_proxy=mv,unique_latent_realizations=len(sample),
                realized_MV_min=min(values),realized_MV_max=max(values),realized_MV_mean=float(np.mean(values)),
                generated_potential=sum(r['N_magnitude_eligible_before_stamp'] for r in sample),
                stamp_lost_potential=sum(r['N_lost_at_stamp'] for r in sample)))
    write_csv(out/'cell_luminosity_and_truncation.csv',cells)
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),replayed_trials=len(rows),
        unique_latent_populations=48,source_sha256=sources,code_sha256=sha(Path(__file__)),
        scope='Exact seeded replay verified against all prepared truth positions, magnitudes and IMF light. No truth rewritten. The magnitude-eligible potential population differs from N_imf; eligible light is not full integrated light. Truncation counts do not measure its effect on recovery. PS1 support uses true LS g/color as a diagnostic against measured-proxy calibration bins, only g0<24.5, and does not validate transfer, classification purity, Eddington bias or physical PS1 completeness. Unsupported bins remain unresolved.'))


if __name__=='__main__':run()
