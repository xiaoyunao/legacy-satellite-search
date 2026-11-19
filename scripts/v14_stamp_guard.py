"""Measure a bounded 30pc truncation correction, without changing the registered 144."""
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

VERSION='v14_stamp_guard'
CONFIG=Path('configs')/VERSION
OUT=Path('results/v14/stamp_guard')
RADIUS=3.1


def prepare():
    data=Path(os.environ['LS_SAT_DATA']);OUT.mkdir(parents=True,exist_ok=True);CONFIG.mkdir(parents=True,exist_ok=True)
    if (OUT/'registration.json').is_file():
        saved=json.loads((OUT/'registration.json').read_text())
        for path,value in saved['source_sha256'].items():
            if sha(Path(path))!=value:raise ValueError('Registered stamp-guard input changed: '+path)
        return
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    plan=yaml.safe_load(Path('configs/v14_repeat/image_trials.yaml').read_text())
    cfg=yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    modelpath,decpath=template_paths(data,cfg);model=load_isochrone(modelpath);dec=load_isochrone(decpath)
    indices,xy,keep,draw,proxy,center=replay(plan,4,model,dec)
    extended=np.linalg.norm(xy,axis=1)<RADIUS-.03
    extra_indices=indices[extended&~keep];extra_positions=xy[extended&~keep]
    with modelpath.open() as f:cols=next(x[1:].split() for x in f if x.startswith('#') and 'int_IMF' in x)
    mags=np.column_stack([model[0],np.loadtxt(modelpath,usecols=[cols.index(b) for b in ('i','z')])])
    ps1path=data/'resources'/plan['ps1_template'];ps1=load_isochrone(ps1path,bands=('gP1','rP1'))
    with ps1path.open() as f:cols=next(x[1:].split() for x in f if x.startswith('#') and 'int_IMF' in x)
    ps1mags=np.column_stack([ps1[0],np.loadtxt(ps1path,usecols=cols.index('iP1'))])
    sources=[modelpath,decpath,ps1path,Path('configs/v14_repeat/image_trials.yaml'),Path('scripts/v13_native.sh')]
    report=[]
    for site in sites:
        name=site['field'];original=data/'image-v14_repeat'/name/'trial04'
        core=np.load(original/'truth.npy',allow_pickle=False);meta=json.loads((original/'truth.json').read_text())
        proof=json.loads(Path('results/v14/repeat/validation/'+name+'-trial04.json').read_text())
        cat,=original.glob('tractor/*/tractor-*.fits')
        if sha(cat)!=proof['tractor_sha256']:raise ValueError('Original accepted control changed')
        if not np.array_equal(core['g0'],mags[indices[keep],0]+20):raise ValueError('Original population replay failed')
        field=local_coordinates(site);ra,dec_=field.sky(*extra_positions.T);ebv=reddening(ra,dec_)
        extra=np.empty(len(extra_indices),dtype=core.dtype);extra['ra']=ra;extra['dec']=dec_
        extra['g0'],extra['r0']=(mags[extra_indices,:2]+20).T
        observed=mags[extra_indices]+20+ebv[:,None]*[3.214,2.165,1.592,1.211]
        for k,b in enumerate('griz'):extra['flux_'+b]=10**(-.4*(observed[:,k]-22.5))
        for k,b in enumerate('gri'):extra['ps1_'+b+'0']=ps1mags[extra_indices,k]+20
        base=data/('image-'+VERSION)/name;base.mkdir(parents=True,exist_ok=True)
        for trial,variant,table in ((0,'extended_3p1_arcmin',np.concatenate([core,extra])),(1,'original_2p47_arcmin',core)):
            folder=base/f'trial{trial:02d}';folder.mkdir(exist_ok=True)
            np.save(folder/'truth.npy',table,allow_pickle=False)
            write_json(folder/'truth.json',dict(meta,trial=trial,latent_population_id=4,realization_id=0,
                N_rendered=len(table),N_original_response=len(core),N_added_outer=len(table)-len(core),guard_variant=variant,
                original_trial=4,scope='One shared 30pc physical draw across the original three backgrounds; conditional radius diagnostic, not three independent populations or a complete infinite-profile correction.'))
            if trial==1:
                for item in ('tractor','injected_exposures.npy','initial_detection.npy'):
                    (folder/item).symlink_to(original/item,target_is_directory=item=='tractor')
            sources.extend([folder/'truth.npy',folder/'truth.json'])
        (base/'blank').symlink_to(data/'image-v14_repeat'/name/'blank',target_is_directory=True)
        sources.extend([original/'truth.npy',original/'truth.json',cat,original/'injected_exposures.npy',original/'initial_detection.npy'])
        report.append(dict(site=name,original_rendered=len(core),extended_rendered=int(extended.sum()),
            eligible_before_stamp=len(indices),outside_extended=int((~extended).sum()),added_outer=len(extra),
            realized_MV_proxy=meta['realized_MV_proxy']))
    write_csv(CONFIG/'image_fields.csv',sites)
    newplan=dict(plan,conditions=[[100,30,-3],[100,30,-3]],splice_radius_arcmin=RADIUS)
    (CONFIG/'image_trials.yaml').write_text(yaml.safe_dump(newplan,sort_keys=False))
    sources.extend([CONFIG/'image_fields.csv',CONFIG/'image_trials.yaml'])
    write_csv(OUT/'population_registration.csv',report)
    write_json(OUT/'registration.json',dict(source_sha256={str(p):sha(p) for p in sources},
        primary_grid_changed=False,original_latent_id=4,extended_radius_arcmin=RADIUS,
        original_radius_arcmin=plan['splice_radius_arcmin'],native_width_px=1536,
        scope='Same native CCD frame and same blank, same original bright-population positions and luminosity. Both variants are measured with the same 3.1 arcmin replacement aperture. Only outer magnitude-eligible stars are added; residual profile tails and unrendered faint light remain outside this diagnostic. No original truth/product is overwritten.'))


def run(name):
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Use an allocated NERSC CPU node')
    prepare();os.environ['LS_SAT_IMAGE_VERSION']=VERSION
    folder=Path(os.environ['LS_SAT_DATA'])/('image-'+VERSION)/name/'trial00'
    if not any(folder.glob('tractor/*/tractor-*.fits')):
        subprocess.run(['bash','scripts/v13_native.sh',name,'trial00'],check=True)
    from scripts import v13_image_trials as measure
    measure.VERSION=VERSION;measure.CONFIG=CONFIG;measure.OUTPUT=Path('results')/VERSION/'image_response'
    measure.measure(name,diagnostics=True)


def accept():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Inspect native arrays on an allocated CPU node')
    data=Path(os.environ['LS_SAT_DATA']);registered=json.loads((OUT/'registration.json').read_text())
    for path,value in registered['source_sha256'].items():
        if sha(Path(path))!=value:raise ValueError('Registered radius-guard input changed: '+path)
    original=read_csv(Path('results/v14/repeat/initial_nine_summary.csv'));rows=[];sources={}
    for site in read_csv(CONFIG/'image_fields.csv'):
        name=site['field'];table=Path('results')/VERSION/'image_response'/(name+'-blind.csv')
        measured=read_csv(table)
        if len(measured)!=4 or {(r['arm'],r['trial']) for r in measured}!={(a,str(t)) for a in ('ls_base','ls_deep') for t in (0,1)}:
            raise ValueError('Missing or duplicate paired radius measurement')
        sources[str(table)]=sha(table)
        for arm in ('ls_base','ls_deep'):
            before=next(r for r in measured if r['arm']==arm and r['trial']=='1')
            after=next(r for r in measured if r['arm']==arm and r['trial']=='0')
            old=next(r for r in original if r['site']==name and r['trial']=='4' and r['arm']==arm)
            if any(before[k]!=old[k] for k in ('N_exposed','N_final','N_psf','N_used')):
                raise ValueError('Unchanged native control source counts differ from original')
            rows.append(dict(site=name,arm=arm,original_N_rendered=int(before['N_rendered']),
                extended_N_rendered=int(after['N_rendered']),original_N_used=int(before['N_used']),
                extended_N_used=int(after['N_used']),original_spatial=before['spatial'],extended_spatial=after['spatial'],
                original_DM=before['blind_dm'],extended_DM=after['blind_dm'],
                original_C_TS=before['c_ts'],extended_C_TS=after['c_ts'],
                original_C_after3=before['c_after_top3'],extended_C_after3=after['c_after_top3'],
                realized_MV_proxy=before['realized_MV_proxy']))
        for trial,n in ((0,274),(1,260)):
            stage=data/('image-'+VERSION)/name/f'trial{trial:02d}'
            exposures=stage/'injected_exposures.npy';counts=np.load(exposures,allow_pickle=False)
            if len(counts)!=n:raise ValueError('Radius-guard native exposure denominator differs')
            sources[str(exposures)]=sha(exposures)
    write_csv(OUT/'paired_comparison.csv',rows)
    write_json(OUT/'acceptance.json',dict(job=os.environ['SLURM_JOB_ID'],backgrounds=3,unique_latent_populations=1,
        paired_arm_comparisons=6,control_native_source_counts_reproduce_original=True,
        original_magnitude_eligible=300,original_rendered=260,extended_rendered=274,residual_outside_extended=26,
        baseline_available_members_before=sum(r['original_N_used'] for r in rows if r['arm']=='ls_base'),
        baseline_available_members_after=sum(r['extended_N_used'] for r in rows if r['arm']=='ls_base'),
        deeper_available_members_before=sum(r['original_N_used'] for r in rows if r['arm']=='ls_deep'),
        deeper_available_members_after=sum(r['extended_N_used'] for r in rows if r['arm']=='ls_deep'),
        spatial_before=sum(r['original_spatial']=='True' for r in rows),spatial_after=sum(r['extended_spatial']=='True' for r in rows),
        sources=sources,registration_sha256=sha(OUT/'registration.json'),code_sha256=sha(Path(__file__)),
        scope='One fixed bright 30pc draw (realized V proxy=-3.770) across the same three backgrounds, all already detectable. The same3.1arcmin replacement aperture is used for both variants, so C/background values need not equal the original2.47arcmin experiment. This tests stage/parameter sensitivity in a ceiling case; it does not measure near-threshold population recovery bias. The extension restores14 of40 truncated magnitude-eligible members;26 remain outside. The primary144 and original9 tables are unchanged.'))
    print('RADIUS_GUARD_ACCEPTED',len(rows),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','accept'));p.add_argument('--site');a=p.parse_args()
    prepare() if a.mode=='prepare' else accept() if a.mode=='accept' else run(a.site)
