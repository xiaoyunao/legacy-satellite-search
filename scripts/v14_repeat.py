"""Register and execute a bounded repeat pilot in a separate native-image namespace."""
import argparse
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv,sha,write_json


def conditions(protocol):
    return [[protocol['distance_kpc'],radius,magnitude]
            for _ in range(protocol['independent_realizations_per_cell'])
            for radius in protocol['radii_pc'] for magnitude in protocol['target_MV_proxy']]


def task(index):
    p=yaml.safe_load(Path('configs/v14_repeat/protocol.yaml').read_text())
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    tasks=[(s['field'],f'trial{i:02d}') for s in sites for i in p['initial_trial_indices']]
    if index<0 or index>=len(tasks): raise ValueError('Invalid registered pilot index')
    return tasks[index]


def prepare():
    from scripts import v13_image_trials as native
    if native.VERSION!='v14_repeat':raise ValueError('Use the v14_repeat.sh environment; refusing to modify a legacy experiment')
    produce=native.produce
    data=Path(os.environ['LS_SAT_DATA']);sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    protocol=Path('configs/v14_repeat/protocol.yaml');spec=yaml.safe_load(protocol.read_text())
    trial_config=Path('configs/v14_repeat/image_trials.yaml');plan=yaml.safe_load(trial_config.read_text())
    if plan['conditions']!=conditions(spec) or plan['seed']!=spec['seed']:
        raise ValueError('Repeat trial grid disagrees with the frozen protocol')
    out=Path('results/v14/repeat');out.mkdir(parents=True,exist_ok=True)
    saved=out/'registration.json'
    checksum=sha(Path('configs/v14_repeat/image_trials.yaml'))
    if saved.exists():
        previous=json.loads(saved.read_text())
        if previous['plan_sha256']!=checksum or previous['protocol_sha256']!=sha(protocol):
            raise ValueError('Repeat plan changed after preparation')
    blanks={}
    for site in sites:
        base=data/'image-v14'/site['field']/'blank'
        tractor=list(base.glob('tractor/*/tractor-*.fits'))
        if len(tractor)!=1: raise ValueError('Missing registered original CCD blank')
        folder=data/'image-v14_repeat'/site['field'];folder.mkdir(parents=True,exist_ok=True)
        link=folder/'blank'
        if not link.exists():link.symlink_to(base,target_is_directory=True)
        if link.resolve()!=base.resolve():raise ValueError('Unexpected repeat blank source')
        produce(site['field']);blanks[site['field']]=sha(tractor[0])
    write_json(saved,dict(job=os.getenv('SLURM_JOB_ID'),plan_sha256=checksum,
        protocol_sha256=sha(Path('configs/v14_repeat/protocol.yaml')),blank_sha256=blanks,
        planned_trials=144,initial_trials=9,scope='Preparation and shared latent PS1/native rows; no recovery result implied.'))


def measure():
    from scripts import v13_image_trials as native
    if native.VERSION!='v14_repeat':raise ValueError('Use the v14_repeat.sh environment')
    actual=native.measure
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    statuses=[];data=Path(os.environ['LS_SAT_DATA'])
    for site in sites:
        folder=data/'image-v14_repeat'/site['field']
        ready=[p for p in folder.glob('trial*') if any(p.glob('tractor/*/tractor-*.fits'))]
        if ready:actual(site['field'],allow_partial=True)
        statuses.append(dict(site=site['field'],ready_trials=len(ready),state='partial_measured' if ready else 'not_measured'))
    out=Path('results/v14/repeat');out.mkdir(parents=True,exist_ok=True)
    write_json(out/'measurement_status.json',dict(job=os.getenv('SLURM_JOB_ID'),sites=statuses,
        scope='Only ready sites measured. Job completion is not completion of all registered trials or PS1 response validation.'))


def validate(field, phase):
    import fitsio
    import numpy as np
    folder=Path(os.environ['LS_SAT_DATA'])/'image-v14_repeat'/field/phase
    cats=list(folder.glob('tractor/*/tractor-*.fits'))
    if len(cats)!=1:raise ValueError('Native run did not produce exactly one Tractor catalogue')
    for name in ('injected_exposures.npy','initial_detection.npy','truth.npy','truth.json'):
        if not (folder/name).is_file():raise ValueError(f'Missing native trial product: {name}')
    truth=json.loads((folder/'truth.json').read_text())
    assert truth['shared_population_rows_verified'] and 'source_poisson_seed' in truth
    with fitsio.FITS(cats[0]) as f:
        columns={n.upper() for n in f[1].get_colnames()}
        if not {'RA','DEC','TYPE','FLUX_G','FLUX_R','FLUX_IVAR_G','FLUX_IVAR_R'}<=columns:
            raise ValueError('Native catalogue lacks mandatory named gr columns')
    out=Path('results/v14/repeat/validation');out.mkdir(parents=True,exist_ok=True)
    write_json(out/f'{field}-{phase}.json',dict(job=os.getenv('SLURM_JOB_ID'),site=field,phase=phase,
        tractor_sha256=sha(cats[0]),truth_sha256=sha(folder/'truth.npy'),
        rendered_stars=len(np.load(folder/'truth.npy',allow_pickle=False)),
        native_products_validated=True,scope='Native product contract only; blind recovery measurement is separate.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('task','prepare','measure','validate'))
    p.add_argument('--field');p.add_argument('--phase')
    p.add_argument('index',type=int,nargs='?');a=p.parse_args()
    if a.mode=='task':print(*task(a.index))
    elif a.mode=='prepare':prepare()
    elif a.mode=='measure':measure()
    else:validate(a.field,a.phase)
