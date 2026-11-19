"""Register and execute a bounded repeat pilot in a separate native-image namespace."""
import argparse
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv,sha,write_csv,write_json


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


def register_remaining():
    """Freeze execution IDs for the existing grid without regenerating stars."""
    config=Path('configs/v14_repeat');out=Path('results/v14/repeat')
    registration=json.loads((out/'registration.json').read_text())
    protocol=config/'protocol.yaml';plan_path=config/'image_trials.yaml'
    if (registration['protocol_sha256']!=sha(protocol) or
            registration['plan_sha256']!=sha(plan_path)):
        raise ValueError('Frozen physical protocol changed')
    spec=yaml.safe_load(protocol.read_text());plan=yaml.safe_load(plan_path.read_text())
    if plan['conditions']!=conditions(spec):raise ValueError('Physical grid mismatch')
    accepted=out/'initial_nine_acceptance.json';proof=json.loads(accepted.read_text())
    if not proof['all_initial_trials_accepted'] or proof['native_trials']!=9:
        raise ValueError('Complete the initial software/resource tranche first')
    for name,checksum in proof['source_sha256'].items():
        if sha(Path(name))!=checksum:raise ValueError('Initial evidence changed: '+name)
    fields=config/'image_fields.csv';sites=read_csv(fields)
    if {r['field'] for r in sites}!=set(registration['blank_sha256']):
        raise ValueError('Registered backgrounds changed')
    cells=len(spec['radii_pc'])*len(spec['target_MV_proxy']);rows=[]
    for trial,cell in enumerate(plan['conditions']):
        if trial in spec['initial_trial_indices']:continue
        for site in sites:
            rows.append(dict(task_index=len(rows),field=site['field'],phase=f'trial{trial:02d}',
                latent_population_id=trial,realization_id=trial//cells,D_kpc=cell[0],
                rh_pc=cell[1],target_MV_proxy=cell[2]))
    path=config/'remaining_tasks.csv';manifest=out/'remaining_registration.json'
    if manifest.exists():
        saved=json.loads(manifest.read_text())
        if sha(path)!=saved['worklist_sha256']:raise ValueError('Remaining task map changed')
        if read_csv(path)!=[{k:str(v) for k,v in r.items()} for r in rows]:
            raise ValueError('Remaining execution map no longer matches registration')
        print('Existing 135-task execution map verified');return
    if len(rows)!=spec['planned_ccd_trials']-proof['native_trials']:
        raise ValueError('Remaining trial count mismatch')
    write_csv(path,rows)
    write_json(manifest,dict(tasks=len(rows),worklist=str(path),worklist_sha256=sha(path),
        protocol_sha256=sha(protocol),plan_sha256=sha(plan_path),fields_sha256=sha(fields),
        initial_acceptance_sha256=sha(accepted),
        scope='Remaining frozen physical realizations only, phase-major across backgrounds. No new random draws, parameter choices or interim gain test. Initial nine and their measured inputs remain unchanged.'))
    print('Registered remaining native tasks:',len(rows),flush=True)


def remaining_task(index):
    saved=json.loads(Path('results/v14/repeat/remaining_registration.json').read_text())
    path=Path(saved['worklist'])
    for name,key in [('configs/v14_repeat/protocol.yaml','protocol_sha256'),
                     ('configs/v14_repeat/image_trials.yaml','plan_sha256'),
                     ('configs/v14_repeat/image_fields.csv','fields_sha256')]:
        if sha(Path(name))!=saved[key]:raise ValueError('Frozen execution inputs changed')
    if sha(path)!=saved['worklist_sha256']:raise ValueError('Remaining task map changed')
    rows=read_csv(path)
    if index is None or not 0<=index<len(rows):raise ValueError('Invalid remaining task index')
    row=rows[index]
    if int(row['task_index'])!=index:raise ValueError('Task index mismatch')
    return row['field'],row['phase']


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


def measure(full=False, require_complete=False, only_field=None):
    from scripts import v13_image_trials as native
    if native.VERSION!='v14_repeat':raise ValueError('Use the v14_repeat.sh environment')
    if full:
        # Keep the accepted initial-tranche tables and their hashes immutable.
        native.OUTPUT=Path('results/v14_repeat_full/image_response')
    actual=native.measure
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    statuses=[];data=Path(os.environ['LS_SAT_DATA'])
    if full and not require_complete:
        requested=[Path('results/v14/repeat/validation')/(site['field']+f'-trial{i:02d}.json')
                   for site in sites for i in range(len(native.context(site['field'])[1]['conditions']))]
        if not all(p.is_file() for p in requested):
            out=Path('results/v14/repeat_full');out.mkdir(parents=True,exist_ok=True)
            write_json(out/'measurement_status.json',dict(job=os.getenv('SLURM_JOB_ID'),
                state='deferred_until_full_native_grid',validated_files=sum(p.is_file() for p in requested),
                expected_files=len(requested),scope='Native tranche finished; no partial science measurement performed. The separate complete-grid measurement job remains required.'))
            print('FULL_MEASUREMENT_DEFERRED: await all registered native trials',flush=True)
            return
    if require_complete:
        # A successful partial measurement must never certify the final grid.
        for site in sites:
            for index in range(len(native.context(site['field'])[1]['conditions'])):
                name=site['field']+f'-trial{index:02d}.json'
                proof=Path('results/v14/repeat/validation')/name
                if not proof.is_file() or not json.loads(proof.read_text())['native_products_validated']:
                    raise ValueError('Unvalidated registered native trial: '+name)
    if only_field:
        if not full or not require_complete:raise ValueError('Per-site measurements require the complete native grid')
        sites=[site for site in sites if site['field']==only_field]
        if len(sites)!=1:raise ValueError('Unknown registered physical background')
    for site in sites:
        folder=data/'image-v14_repeat'/site['field']
        ready=[p for p in folder.glob('trial*') if any(p.glob('tractor/*/tractor-*.fits'))]
        if ready:actual(site['field'],allow_partial=not require_complete,diagnostics=full)
        statuses.append(dict(site=site['field'],ready_trials=len(ready),
            state='complete_measured' if len(ready)==len(native.context(site['field'])[1]['conditions'])
            else 'partial_measured' if ready else 'not_measured'))
    out=Path('results/v14/repeat_full' if full else 'results/v14/repeat');out.mkdir(parents=True,exist_ok=True)
    write_json(out/((only_field+'-measurement_status.json') if only_field else 'measurement_status.json'),dict(job=os.getenv('SLURM_JOB_ID'),sites=statuses,
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
    proof=out/f'{field}-{phase}.json';cat_hash=sha(cats[0]);truth_hash=sha(folder/'truth.npy')
    if proof.is_file():
        old=json.loads(proof.read_text())
        if not (old.get('native_products_validated') and old.get('site')==field and old.get('phase')==phase
                and old['tractor_sha256']==cat_hash and old['truth_sha256']==truth_hash):
            raise ValueError('Previously validated native inputs changed: '+str(proof))
        print('EXISTING_NATIVE_VALIDATION_PRESERVED',field,phase,flush=True)
        return
    write_json(proof,dict(job=os.getenv('SLURM_JOB_ID'),site=field,phase=phase,
        tractor_sha256=cat_hash,truth_sha256=truth_hash,
        rendered_stars=len(np.load(folder/'truth.npy',allow_pickle=False)),
        native_products_validated=True,scope='Native product contract only; blind recovery measurement is separate.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('task','prepare','measure','validate','register_remaining','remaining','measure_full','measure_complete','measure_site'))
    p.add_argument('--field');p.add_argument('--phase')
    p.add_argument('index',type=int,nargs='?');a=p.parse_args()
    if a.mode=='task':print(*task(a.index))
    elif a.mode=='register_remaining':register_remaining()
    elif a.mode=='remaining':print(*remaining_task(a.index))
    elif a.mode=='prepare':prepare()
    elif a.mode in ('measure','measure_full','measure_complete'):
        measure(full=a.mode!='measure',require_complete=a.mode=='measure_complete')
    elif a.mode=='measure_site':
        if not a.field:p.error('measure_site requires --field')
        measure(full=True,require_complete=True,only_field=a.field)
    else:validate(a.field,a.phase)
