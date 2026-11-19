"""Test the single mixed-background30pc draw, keeping the primary144 unchanged."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import yaml

from ls_satsearch.matched import reddening
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone
from scripts.v13_image_trials import local_coordinates, template_paths
from scripts.v14_repeat_population_audit import replay

VERSION = 'v14_stamp_boundary'
CONFIG = Path('configs')/VERSION
OUT = Path('results/v14/stamp_boundary')
ORIGINAL_TRIAL = 34
RADIUS = 3.1


def prepare():
    if not os.getenv('SLURM_JOB_ID'):
        raise ValueError('Read image truth on a compute node')
    registration = OUT/'registration.json'
    if registration.exists():
        for name, digest in json.loads(registration.read_text())['source_sha256'].items():
            if sha(Path(name)) != digest:raise ValueError('Registered boundary input changed')
        return
    data = Path(os.environ['LS_SAT_DATA'])
    source = Path('results/v14/repeat_full/full_summary.csv')
    measured = read_csv(source)
    candidates = []
    for trial in range(4,48,6):
        rows = [r for r in measured if int(r['trial']) == trial and r['arm']=='ls_base']
        if 0 < sum(r['spatial']=='True' for r in rows) < 3:candidates.append(trial)
    if candidates != [ORIGINAL_TRIAL]:
        raise ValueError('Expected the unique mixed-background bright30pc draw')
    plan = yaml.safe_load(Path('configs/v14_repeat/image_trials.yaml').read_text())
    cfg = yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    modelpath, decpath = template_paths(data,cfg)
    model,decam = load_isochrone(modelpath),load_isochrone(decpath)
    indices,xy,keep,_,_,_ = replay(plan,ORIGINAL_TRIAL,model,decam)
    extended = np.linalg.norm(xy,axis=1) < RADIUS-.03
    with modelpath.open() as stream:
        columns=next(line[1:].split() for line in stream if line.startswith('#') and 'int_IMF' in line)
    mags=np.column_stack([model[0],np.loadtxt(modelpath,usecols=[columns.index(b) for b in ('i','z')])])
    ps1path=data/'resources'/plan['ps1_template']
    ps1=load_isochrone(ps1path,bands=('gP1','rP1'))
    with ps1path.open() as stream:
        columns=next(line[1:].split() for line in stream if line.startswith('#') and 'int_IMF' in line)
    ps1mags=np.column_stack([ps1[0],np.loadtxt(ps1path,usecols=columns.index('iP1'))])
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    OUT.mkdir(parents=True,exist_ok=True);CONFIG.mkdir(parents=True,exist_ok=True)
    sources=[source,modelpath,decpath,ps1path,Path(__file__),Path('scripts/v13_native.sh'),
        Path('scripts/v13_native.py'),Path('configs/v14_repeat/image_trials.yaml')]
    counts=[]
    for site in sites:
        name=site['field'];original=data/'image-v14_repeat'/name/f'trial{ORIGINAL_TRIAL:02d}'
        core=np.load(original/'truth.npy',allow_pickle=False);meta=json.loads((original/'truth.json').read_text())
        proof_path=Path('results/v14/repeat/validation')/f'{name}-trial{ORIGINAL_TRIAL:02d}.json'
        proof=json.loads(proof_path.read_text());cat,=original.glob('tractor/*/tractor-*.fits')
        if sha(cat)!=proof['tractor_sha256'] or sha(original/'truth.npy')!=proof['truth_sha256']:
            raise ValueError('Accepted primary trial changed')
        field=local_coordinates(site)
        if not np.array_equal(core['g0'],mags[indices[keep],0]+20) or not np.allclose(np.column_stack(field.xy(core['ra'],core['dec'])),xy[keep],atol=1e-7,rtol=0):
            raise ValueError('Original IMF or positions do not reproduce')
        extra_ids=indices[extended&~keep];positions=xy[extended&~keep]
        ra,dec=field.sky(*positions.T);ebv=reddening(ra,dec)
        extra=np.empty(len(extra_ids),dtype=core.dtype);extra['ra']=ra;extra['dec']=dec
        extra['g0'],extra['r0']=(mags[extra_ids,:2]+20).T
        observed=mags[extra_ids]+20+ebv[:,None]*[3.214,2.165,1.592,1.211]
        for k,b in enumerate('griz'):extra['flux_'+b]=10**(-.4*(observed[:,k]-22.5))
        for k,b in enumerate('gri'):extra['ps1_'+b+'0']=ps1mags[extra_ids,k]+20
        base=data/('image-'+VERSION)/name;base.mkdir(parents=True,exist_ok=True)
        for trial,table in ((0,np.concatenate([core,extra])),(1,core)):
            folder=base/f'trial{trial:02d}';folder.mkdir(exist_ok=True)
            np.save(folder/'truth.npy',table,allow_pickle=False)
            write_json(folder/'truth.json',dict(meta,trial=trial,latent_population_id=ORIGINAL_TRIAL,
                realization_id=ORIGINAL_TRIAL//6,N_rendered=len(table),original_trial=ORIGINAL_TRIAL,
                N_original_response=len(core),N_added_outer=len(table)-len(core),
                guard_variant='extended' if trial==0 else 'original',
                scope='Outcome-targeted boundary diagnostic, one IMF draw across three backgrounds; not an unbiased population correction.'))
            if trial==1:
                for item in ('tractor','injected_exposures.npy','initial_detection.npy'):
                    (folder/item).symlink_to(original/item,target_is_directory=item=='tractor')
            sources.extend([folder/'truth.npy',folder/'truth.json'])
        (base/'blank').symlink_to(data/'image-v14_repeat'/name/'blank',target_is_directory=True)
        sources.extend([proof_path,original/'truth.npy',original/'truth.json',cat])
        counts.append(dict(site=name,original_trial=ORIGINAL_TRIAL,original_rendered=len(core),
            extended_rendered=int(extended.sum()),eligible_before_stamp=len(indices),
            residual_outside_extended=int((~extended).sum()),realized_MV_proxy=meta['realized_MV_proxy']))
    write_csv(CONFIG/'image_fields.csv',sites)
    (CONFIG/'image_trials.yaml').write_text(yaml.safe_dump(dict(plan,conditions=[plan['conditions'][ORIGINAL_TRIAL]]*2,splice_radius_arcmin=RADIUS),sort_keys=False))
    sources.extend([CONFIG/'image_fields.csv',CONFIG/'image_trials.yaml'])
    write_csv(OUT/'population_registration.csv',counts)
    write_json(registration,dict(source_sha256={str(p):sha(p) for p in sources},
        selected_original_trial=ORIGINAL_TRIAL,selection_rule='Unique target−3/30pc draw with mixed baseline recovery across three backgrounds in the completed144 experiment.',
        primary_grid_unchanged=True,original_radius_arcmin=plan['splice_radius_arcmin'],extended_radius_arcmin=RADIUS,
        scope='Same1536pixel frames, original stars/positions and source photon seed. Add only omitted magnitude-eligible outer members. Both variants use the same3.1arcmin splice and legacy matched policy. Reused seed does not ensure identical original-star Poisson pixel noise after adding sources. Residual tails/faint light remain; no full completeness or all-sky bias correction.'))
    print('BOUNDARY_DIAGNOSTIC_REGISTERED',counts,flush=True)


def run(site):
    prepare();os.environ['LS_SAT_IMAGE_VERSION']=VERSION
    folder=Path(os.environ['LS_SAT_DATA'])/('image-'+VERSION)/site/'trial00'
    if not any(folder.glob('tractor/*/tractor-*.fits')):
        subprocess.run(['bash','scripts/v13_native.sh',site,'trial00'],check=True)
    from scripts import v13_image_trials as measure
    measure.VERSION=VERSION;measure.CONFIG=CONFIG;measure.OUTPUT=Path('results')/VERSION/'image_response'
    measure.measure(site,diagnostics=True)


def accept():
    prepare()
    data=Path(os.environ['LS_SAT_DATA'])
    original=read_csv(Path('results/v14/repeat_full/full_summary.csv'))
    sources={str(OUT/'registration.json'):sha(OUT/'registration.json')};paired=[]
    for site in read_csv(CONFIG/'image_fields.csv'):
        name=site['field'];path=Path('results')/VERSION/'image_response'/(name+'-blind.csv')
        rows=read_csv(path)
        if len(rows)!=4 or {(r['arm'],r['trial']) for r in rows}!={(a,str(t)) for a in ('ls_base','ls_deep') for t in (0,1)}:
            raise ValueError('Incomplete paired boundary measurement')
        sources[str(path)]=sha(path)
        for trial in (0,1):
            stage=data/('image-'+VERSION)/name/f'trial{trial:02d}'
            truth=np.load(stage/'truth.npy',allow_pickle=False)
            exposed=np.load(stage/'injected_exposures.npy',allow_pickle=False)
            if len(truth)!=len(exposed):raise ValueError('Exposure denominator differs')
            for file in [stage/'truth.npy',stage/'truth.json',stage/'injected_exposures.npy',*stage.glob('tractor/*/tractor-*.fits')]:sources[str(file)]=sha(file)
        for arm in ('ls_base','ls_deep'):
            before=next(r for r in rows if r['arm']==arm and r['trial']=='1')
            after=next(r for r in rows if r['arm']==arm and r['trial']=='0')
            prior=next(r for r in original if r['site']==name and r['arm']==arm and int(r['trial'])==ORIGINAL_TRIAL)
            if any(before[key]!=prior[key] for key in ('N_exposed','N_final','N_psf','N_used')):
                raise ValueError('Unchanged native control stage counts do not reproduce')
            record=dict(site=name,arm=arm,latent_population_id=ORIGINAL_TRIAL,realized_MV_proxy=before['realized_MV_proxy'])
            for key in ('N_rendered','N_exposed','N_final','N_psf','N_used','spatial','blind_dm','blind_correct','correct_mode_exists','c_ts','c_after_top3'):
                record['original_'+key]=before[key];record['extended_'+key]=after[key]
            paired.append(record)
    write_csv(OUT/'paired_comparison.csv',paired)
    write_json(OUT/'acceptance.json',dict(job=os.environ['SLURM_JOB_ID'],paired_arm_cases=6,
        unique_latent_populations=1,original_controls_reproduced=True,input_sha256=sources,
        original_spatial=sum(r['original_spatial']=='True' for r in paired),
        extended_spatial=sum(r['extended_spatial']=='True' for r in paired),
        scope='Outcome-targeted near-boundary draw34, three selected backgrounds. Same native frame/old members; add outer members and use common larger splice. Shared photon seed does not imply identical inner pixel noise. Residual tails and faint omitted light remain. Quantifies this conditional sensitivity, not an unbiased population completeness correction or formal-production PS1 increment.'))
    print('BOUNDARY_DIAGNOSTIC_ACCEPTED',len(paired),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','accept'));p.add_argument('--site');a=p.parse_args()
    prepare() if a.mode=='prepare' else accept() if a.mode=='accept' else run(a.site)
