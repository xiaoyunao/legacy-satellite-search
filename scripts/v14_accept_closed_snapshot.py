"""Accept finished regional/catalogue stages separately from an atlas timeout."""
import json
import os
from pathlib import Path

from ls_satsearch.run import sha, write_json


def run():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Run the source audit on Slurm')
    root=Path('results/v14')
    status_path=root/'discovery/status.json';catalogue_path=root/'catalogue/manifest.json'
    status=json.loads(status_path.read_text());catalogue=json.loads(catalogue_path.read_text())
    if status['job']!='61470267' or catalogue['job']!='61470267':
        raise ValueError('Expected the actual closed-source snapshot owner')
    layers=status['layers']
    if (sum(r['registered'] for r in layers)!=6891 or
            any(r['completed']+r['no_usable']!=r['registered'] for r in layers)):
        raise ValueError('Regional aggregate is not terminal')
    inputs={str(p):sha(p) for p in (status_path,catalogue_path,
        root/'catalogue/candidate_modes.csv',root/'catalogue/candidate_catalogue.csv',
        root/'catalogue/potential_associations_within_5arcmin.csv')}
    inputs.update(catalogue['inputs'])
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Source changed: '+name)
    write_json(root/'production_integration/checkpoints/outside_C_final_20261120/closed_snapshot_acceptance.json',
        dict(job=os.environ['SLURM_JOB_ID'],source_job='61470267',inputs=inputs,
            registered_fields=6891,all_regional_sources_terminal=True,
            catalogue_source_hashes_verified=True,atlas_complete=False,
            scope='Accept already-finished regional and catalogue stages only; no repeated scan, C fit or peak evaluation. Atlas/science-tail and historical production/area integration remain separate.'))
    print('CLOSED_REGIONAL_CATALOGUE_ACCEPTED',flush=True)


if __name__=='__main__':run()
