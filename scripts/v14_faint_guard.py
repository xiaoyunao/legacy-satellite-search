"""A registered single-case unresolved-faint-light diagnostic, separate from the 144 trials."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import yaml

from ls_satsearch.matched import reddening
from ls_satsearch.run import read_csv,sha,write_csv,write_json
from ls_satsearch.search import load_isochrone
from scripts.v13_image_trials import local_coordinates,template_paths
from scripts.v14_repeat_population_audit import replay


def prepare():
    data=Path(os.environ['LS_SAT_DATA']);out=Path('results/v14/faint_guard');out.mkdir(parents=True,exist_ok=True)
    config=Path('configs/v14_faint_guard');config.mkdir(parents=True,exist_ok=True)
    site=read_csv(Path('configs/v14_repeat/image_fields.csv'))[0]
    name=site['field'];original=data/'image-v14_repeat'/name/'trial00'
    base=data/'image-v14_faint_guard'/name;base.mkdir(parents=True,exist_ok=True)
    if (out/'registration.json').exists():
        saved=json.loads((out/'registration.json').read_text())
        for path,checksum in saved['source_sha256'].items():
            if sha(Path(path))!=checksum:raise ValueError('Registered guard input changed: '+path)
        return name
    spec=yaml.safe_load(Path('configs/v14_repeat/image_trials.yaml').read_text())
    cfg=yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    native_path,decam_path=template_paths(data,cfg)
    model=load_isochrone(native_path);decam=load_isochrone(decam_path)
    core=np.load(original/'truth.npy',allow_pickle=False);meta=json.loads((original/'truth.json').read_text())
    cats=list(original.glob('tractor/*/tractor-*.fits'))
    proof=json.loads(Path('results/v14/repeat/validation/'+name+'-trial00.json').read_text())
    if len(cats)!=1 or sha(cats[0])!=proof['tractor_sha256']:
        raise ValueError('Original accepted native control changed')
    if meta['model_sha256']!=sha(native_path):raise ValueError('Original stellar template changed')
    indices,xy,keep,draw,proxy,center=replay(spec,0,model,decam)
    if not np.array_equal(core['g0'],model[0][indices[keep],0]+20):raise ValueError('Response truth replay failed')
    valid=np.any(np.column_stack([model[0],decam[0]])<np.array([26,25.5]*2)-20,axis=1)
    faint=np.repeat(np.arange(len(draw)),draw*~valid)
    rng=np.random.default_rng([spec['seed'],0,74217]);q=rng.random(len(faint));angle=rng.uniform(0,2*np.pi,len(faint))
    positions=center+(meta['theta_h_arcmin']*np.sqrt(q/(1-q)))[:,None]*np.column_stack([np.cos(angle),np.sin(angle)])
    within=np.linalg.norm(positions,axis=1)<spec['splice_radius_arcmin']-.03
    faint=faint[within];positions=positions[within]
    with native_path.open() as handle:
        cols=next(x[1:].split() for x in handle if x.startswith('#') and 'int_IMF' in x)
    mags=np.column_stack([model[0],np.loadtxt(native_path,usecols=[cols.index(b) for b in ('i','z')])])
    ps1_path=data/'resources'/spec['ps1_template'];ps1_model=load_isochrone(ps1_path,bands=('gP1','rP1'))
    with ps1_path.open() as handle:
        cols=next(x[1:].split() for x in handle if x.startswith('#') and 'int_IMF' in x)
    ps1=np.column_stack([ps1_model[0],np.loadtxt(ps1_path,usecols=cols.index('iP1'))])
    if meta['ps1_model_sha256']!=sha(ps1_path):raise ValueError('Original PS1 physical rows changed')
    field=local_coordinates(site);ra,dec=field.sky(*positions.T);ebv=reddening(ra,dec)
    extra=np.empty(len(faint),dtype=core.dtype);extra['ra']=ra;extra['dec']=dec
    extra['g0'],extra['r0']=(mags[faint,:2]+20).T
    flux=10**(-.4*(mags[faint]+20+ebv[:,None]*[3.214,2.165,1.592,1.211]-22.5))
    for i,b in enumerate('griz'):extra['flux_'+b]=flux[:,i]
    for i,b in enumerate(('g','r','i')):extra['ps1_'+b+'0']=ps1[faint,i]+20
    injected=base/'trial00';control=base/'trial01'
    injected.mkdir(exist_ok=True);control.mkdir(exist_ok=True)
    np.save(injected/'render_sources.npy',np.concatenate([core,extra]),allow_pickle=False)
    for folder,trial,variant in ((injected,0,'all_IMF_faint_flux_added'),(control,1,'original_generation_limit')):
        shutil.copy2(original/'truth.npy',folder/'truth.npy')
        write_json(folder/'truth.json',dict(meta,trial=trial,latent_population_id=0,realization_id=0,
            guard_variant=variant,original_trial=0,N_rendered_all=len(core)+len(extra) if trial==0 else len(core),
            N_faint_added=len(extra) if trial==0 else 0,
            guard_scope='N_rendered and standard attrition refer to the unchanged original response-star set. All pixel-rendered and faint exposure counts are separate. Not an additional independent IMF realization.'))
    for item in ('tractor','injected_exposures.npy','initial_detection.npy'):
        (control/item).symlink_to(original/item,target_is_directory=item=='tractor')
    (base/'blank').symlink_to(data/'image-v14_repeat'/name/'blank',target_is_directory=True)
    write_csv(config/'image_fields.csv',[site]);plan=dict(spec,conditions=[[100,3,-3],[100,3,-3]])
    (config/'image_trials.yaml').write_text(yaml.safe_dump(plan,sort_keys=False))
    source=Path('scripts/v13_native.sh');runner=Path('logs/v14-faint-native-runner.sh')
    text=source.read_text();needle='$workspace/scripts/v13_native.py'
    if text.count(needle)!=1:raise ValueError('Native wrapper changed; review the guard adapter')
    runner.write_text(text.replace(needle,'$workspace/scripts/v14_faint_native.py'))
    sources=[original/'truth.npy',original/'truth.json',cats[0],original/'injected_exposures.npy',
        original/'initial_detection.npy',native_path,ps1_path,source,runner,
        config/'image_fields.csv',config/'image_trials.yaml',injected/'truth.npy',injected/'truth.json',injected/'render_sources.npy',control/'truth.json']
    write_json(out/'registration.json',dict(source_sha256={str(p):sha(p) for p in sources},
        original_site=name,original_trial=0,response_stars=len(core),added_faint_stars=len(extra),
        actual_rendered_stars=len(core)+len(extra),faint_position_seed=[spec['seed'],0,74217],
        scope='One deliberately selected previously failed 3pc/100kpc bright-cell case. Shared original IMF draw, bright-star positions and original image/control; only previously unrendered faint flux added. Native marginal photon noise remains physical; identical random seeds do not imply identical pixel noise after the flux changes. No population recovery/gain estimate and no change to the primary 144.'))
    return name


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Run the real-image guard on an allocated CPU node')
    name=prepare()
    os.environ['LS_SAT_IMAGE_VERSION']='v14_faint_guard'
    folder=Path(os.environ['LS_SAT_DATA'])/'image-v14_faint_guard'/name/'trial00'
    if not any(folder.glob('tractor/*/tractor-*.fits')):
        subprocess.run(['bash','logs/v14-faint-native-runner.sh',name,'trial00'],check=True)
    from scripts import v13_image_trials as measure
    measure.VERSION='v14_faint_guard';measure.CONFIG=Path('configs/v14_faint_guard')
    measure.OUTPUT=Path('results/v14_faint_guard/image_response')
    measure.measure(name,diagnostics=True)


def accept():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Inspect native arrays on an allocated CPU node')
    out=Path('results/v14/faint_guard');saved=json.loads((out/'registration.json').read_text())
    for path,value in saved['source_sha256'].items():
        if sha(Path(path))!=value:raise ValueError('Registered guard input changed: '+path)
    table=Path('results/v14_faint_guard/image_response')/(saved['original_site']+'-blind.csv')
    rows=read_csv(table)
    if {(r['arm'],int(r['trial'])) for r in rows}!={(a,t) for a in ('ls_base','ls_deep') for t in (0,1)} or len(rows)!=4:
        raise ValueError('Missing or duplicate paired guard measurement')
    original=read_csv(Path('results/v14/repeat/initial_nine_summary.csv'))
    for arm in ('ls_base','ls_deep'):
        now=next(r for r in rows if r['arm']==arm and r['trial']=='1')
        old=next(r for r in original if r['site']==saved['original_site'] and r['trial']=='0' and r['arm']==arm)
        if any(now[k]!=old[k] for k in ('N_exposed','N_final','N_psf','N_used','spatial','correct_mode_exists','blind_correct')):
            raise ValueError('Reused control does not reproduce accepted original: '+arm)
    root=Path(os.environ['LS_SAT_DATA'])/'image-v14_faint_guard'/saved['original_site']/'trial00'
    all_exposures=root/'injected_exposures_all_rendered.npy';nobs=np.load(all_exposures,allow_pickle=False)
    exposed=(nobs[:,:2]>0).all(axis=1);n=saved['response_stars']
    if len(nobs)!=saved['actual_rendered_stars']:raise ValueError('Incomplete faint-source exposure array')
    write_json(out/'acceptance.json',dict(job=os.environ['SLURM_JOB_ID'],paired_measurements=4,
        registered_sources_verified=True,control_reproduces_initial=True,all_pixel_sources=len(nobs),
        original_response_stars=n,added_faint_stars=len(nobs)-n,
        pixel_sources_with_positive_gr_exposure=int(exposed.sum()),
        original_with_positive_gr_exposure=int(exposed[:n].sum()),
        faint_with_positive_gr_exposure=int(exposed[n:].sum()),
        sources={str(p):sha(p) for p in (out/'registration.json',table,all_exposures)},
        scope='Native exposure counts verified for all rendered sources. Standard recovery and attrition denominators remain the original response stars. One deliberately selected paired case, not a physical completeness or global faint-light correction.'))
    print('FAINT_GUARD_ACCEPTED',len(nobs),int(exposed.sum()),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','accept'));a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='accept':accept()
    else:run()
