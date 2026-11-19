"""Hold the rendered stellar population fixed and test native size-response stages."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from time import monotonic

import numpy as np
import yaml

from ls_satsearch.matched import reddening
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts import v13_image_trials as native

VERSION='v14_paired_radius'
CONFIG=Path('configs')/VERSION
OUT=Path('results/v14/paired_radius')


def light_radius(table, field, center):
    xy=np.column_stack(field.xy(table['ra'],table['dec']))-center
    radius=np.linalg.norm(xy,axis=1)
    weight=10**(-.4*(table['g0']-.59*(table['g0']-table['r0'])-.01-20))
    order=np.argsort(radius)
    half=radius[order][np.searchsorted(np.cumsum(weight[order]),weight.sum()/2)]
    return float(weight.sum()),float(half)


def prepare():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Read raw truth and SFD on a compute node')
    registration=OUT/'registration.json'
    if registration.exists():
        for p,digest in json.loads(registration.read_text())['inputs'].items():
            if sha(Path(p))!=digest:raise ValueError('Frozen radius-stage input changed: '+p)
        return
    spec=yaml.safe_load((CONFIG/'protocol.yaml').read_text())
    if spec['parent_condition']!=[100,10,-3.0] or spec['new_Plummer_rh_pc']!=3 or spec['planned_new_native_cases']!=24:raise ValueError('Protocol differs from this bounded experiment')
    data=Path(os.environ['LS_SAT_DATA']);plan_path=Path('configs/v14_repeat/image_trials.yaml')
    plan=yaml.safe_load(plan_path.read_text());sites_path=Path('configs/v14_repeat/image_fields.csv');sites=read_csv(sites_path)
    parents=[i for i,cell in enumerate(plan['conditions']) if cell==[100,10,-3.0]]
    if len(parents)!=8 or len(sites)!=3:raise ValueError('Require all eight parent populations and three original backgrounds')
    inputs=[CONFIG/'protocol.yaml',Path(__file__),plan_path,sites_path,Path('results/v14/repeat_full/full_summary.csv'),Path('scripts/v13_native.py'),Path('scripts/v13_native.sh'),Path('scripts/v14_paired_radius.sh'),Path('scripts/v13_image_trials.py'),
        Path('configs/v13/matched/south/search.yaml'),Path('configs/v13/matched/south/matched.yaml'),
        Path('src/ls_satsearch/data.py'),Path('src/ls_satsearch/matched.py'),Path('src/ls_satsearch/search.py')]
    parent_cfg=yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text());inputs.append(native.template_paths(data,parent_cfg)[0])
    records=[];tasks=[];new_plan=dict(plan,conditions=[[100,3,-3.0] for _ in parents],parent_trials=parents)
    OUT.mkdir(parents=True,exist_ok=True)
    for k,trial in enumerate(parents):
        population_reference=None
        for site in sites:
            name=site['field'];old=data/'image-v14_repeat'/name/f'trial{trial:02d}'
            proof_path=Path('results/v14/repeat/validation')/f'{name}-trial{trial:02d}.json'
            proof=json.loads(proof_path.read_text());table=np.load(old/'truth.npy',allow_pickle=False);meta=json.loads((old/'truth.json').read_text())
            cat,=old.glob('tractor/*/tractor-*.fits')
            if sha(cat)!=proof['tractor_sha256'] or sha(old/'truth.npy')!=proof['truth_sha256']:raise ValueError('Accepted parent changed')
            if (meta['D_kpc'],meta['rh_pc'],meta['expected_MV_proxy'])!=(100,10,-3):raise ValueError('Wrong parent condition')
            field=native.local_coordinates(site);center=np.asarray(field.xy(meta['truth_ra_deg'],meta['truth_dec_deg']))
            xy=np.column_stack(field.xy(table['ra'],table['dec']))
            current=(np.column_stack([table['g0'],table['r0']]),xy-center,meta['N_imf'],meta['realized_MV_proxy'])
            if population_reference is None:population_reference=current
            elif (not np.array_equal(current[0],population_reference[0]) or not np.allclose(current[1],population_reference[1],atol=1e-7,rtol=0) or current[2]!=population_reference[2] or not np.isclose(current[3],population_reference[3],atol=1e-12,rtol=0)):raise ValueError('Parent populations are not shared across backgrounds')
            theta=np.rad2deg(np.arctan(3/100000))*60;ratio=theta/meta['theta_h_arcmin']
            smaller=table.copy();ra,dec=field.sky(*(center+(xy-center)*ratio).T);smaller['ra']=ra;smaller['dec']=dec
            old_ebv=reddening(table['ra'],table['dec']);new_ebv=reddening(ra,dec);delta=new_ebv-old_ebv
            if not np.isfinite(delta).all():raise ValueError('Invalid SFD at a paired position')
            for band,coefficient in zip('griz',(3.214,2.165,1.592,1.211)):
                smaller['flux_'+band]*=10**(-.4*coefficient*delta)
                before=table['flux_'+band]*10**(.4*coefficient*old_ebv)
                after=smaller['flux_'+band]*10**(.4*coefficient*new_ebv)
                if not np.allclose(before,after,rtol=1e-12,atol=0):raise ValueError('Intrinsic band flux changed')
            for key in table.dtype.names:
                if key not in ('ra','dec') and not key.startswith('flux_') and not np.array_equal(table[key],smaller[key]):raise ValueError('Member identity or intrinsic magnitude changed')
            old_light,old_half=light_radius(table,field,center);new_light,new_half=light_radius(smaller,field,center)
            if old_light!=new_light or not np.isclose(new_half,old_half*ratio,atol=1e-7,rtol=0):raise ValueError('Light or spatial scaling changed')
            base=data/('image-'+VERSION)/name;base.mkdir(parents=True,exist_ok=True)
            if not (base/'blank').exists():(base/'blank').symlink_to(data/'image-v14_repeat'/name/'blank',target_is_directory=True)
            folder=base/f'trial{k:02d}';folder.mkdir(exist_ok=True)
            np.save(folder/'truth.npy',smaller,allow_pickle=False)
            write_json(folder/'truth.json',dict(meta,trial=k,rh_pc=3,theta_h_arcmin=theta,original_trial=trial,
                latent_population_id=trial,realization_id=k,paired_original_rh_pc=10,source_poisson_seed=meta.get('source_poisson_seed',483423),
                paired_member_identity='unchanged parent truth-row ordinal',paired_radius_stage_only=True,
                scope='Same original finite rendered stellar list and intrinsic luminosities; positions shrink about the same true centre. Local extinction is recomputed. Parent faint/stamp exclusions remain. No new IMF draw or blind recovery claim.'))
            record=dict(site=name,new_trial=k,original_trial=trial,latent_population_id=trial,N_imf=meta['N_imf'],N_rendered=len(table),
                full_IMF_realized_MV_proxy=meta['realized_MV_proxy'],same_rendered_MV_proxy=-2.5*np.log10(old_light),
                parent_light_half_radius_arcmin=old_half,new_light_half_radius_arcmin=new_half,
                angular_scale_ratio=ratio,ebv_delta_abs_max=float(np.max(np.abs(delta))),
                parent_truth_sha256=sha(old/'truth.npy'),new_truth_sha256=sha(folder/'truth.npy'))
            blank_cat,= (data/'image-v14_repeat'/name/'blank').glob('tractor/*/tractor-*.fits');inputs.extend([blank_cat,data/'image-v14_repeat'/name/'blank/initial_detection.npy'])
            records.append(record);tasks.append(dict(task_index=len(tasks),site=name,new_trial=k,original_trial=trial))
            inputs.extend([proof_path,old/'truth.npy',old/'truth.json',cat,folder/'truth.npy',folder/'truth.json'])
    write_csv(CONFIG/'image_fields.csv',sites);(CONFIG/'image_trials.yaml').write_text(yaml.safe_dump(new_plan,sort_keys=False))
    write_csv(CONFIG/'tasks.csv',tasks);write_csv(OUT/'input_population_pairs.csv',records)
    inputs.extend([CONFIG/'image_fields.csv',CONFIG/'image_trials.yaml',CONFIG/'tasks.csv'])
    write_json(registration,dict(job=os.getenv('SLURM_JOB_ID'),inputs={str(p):sha(p) for p in inputs},
        new_cases=24,shared_parent_populations=8,backgrounds=3,original_trials=parents,
        original_144_unchanged=True,shared_members_and_spatial_realization_across_backgrounds_verified=True,blind_search_performed=False,planned_stage_code_sha256=sha(Path('scripts/v14_paired_radius_stages.py')),scope=yaml.safe_load((CONFIG/'protocol.yaml').read_text())['scope']))
    print('PAIRED_RADIUS_REGISTERED',len(tasks),flush=True)


def run_native(index):
    prepare();rows=read_csv(CONFIG/'tasks.csv')
    if not 0<=index<len(rows):raise ValueError('Invalid registered task')
    row=rows[index];site=row['site'];trial=int(row['new_trial']);folder=Path(os.environ['LS_SAT_DATA'])/('image-'+VERSION)/site/f'trial{trial:02d}'
    os.environ['LS_SAT_IMAGE_VERSION']=VERSION
    proof=OUT/'native_validation'/f'{site}-trial{trial:02d}.json'
    if proof.exists():
        for p,digest in json.loads(proof.read_text())['inputs'].items():
            if sha(Path(p))!=digest:raise ValueError('Accepted native case changed')
        return
    started=monotonic()
    ready=len(list(folder.glob('tractor/*/tractor-*.fits')))==1 and all((folder/name).is_file() for name in ('injected_exposures.npy','initial_detection.npy'))
    if not ready:subprocess.run(['bash','scripts/v13_native.sh',site,f'trial{trial:02d}'],check=True)
    table,cat=native.native_table(folder);truth=np.load(folder/'truth.npy',allow_pickle=False)
    exposed=np.load(folder/'injected_exposures.npy',allow_pickle=False);initial=np.load(folder/'initial_detection.npy',allow_pickle=False)
    if exposed.shape!=(len(truth),4) or initial.ndim!=2 or initial.shape[1]!=2 or not len(table):raise ValueError('Incomplete native outputs')
    files=[folder/'truth.npy',folder/'truth.json',folder/'injected_exposures.npy',folder/'initial_detection.npy',cat]
    proof.parent.mkdir(parents=True,exist_ok=True)
    write_json(proof,dict(job=os.getenv('SLURM_JOB_ID'),task_index=index,site=site,new_trial=trial,original_trial=int(row['original_trial']),native_seconds=None if ready else monotonic()-started,reused_existing_complete_native_products=ready,inputs={str(p):sha(p) for p in files},scope='Native image/extraction product proof only; source-response stage measurements remain separate.'))
    print('PAIRED_RADIUS_NATIVE_ACCEPTED',index,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','native','pilot','full_stages'));p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='native':run_native(a.index)
    elif a.mode=='pilot':
        from scripts.v14_paired_radius_stages import stage_measurements
        for i in (0,1,2):run_native(i)
        stage_measurements([0,1,2],'pilot')
    else:
        from scripts.v14_paired_radius_stages import stage_measurements
        stage_measurements(list(range(24)),'full')
