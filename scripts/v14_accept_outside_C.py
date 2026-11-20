"""Accept terminal outside-census C shards; retain every missing/failed state."""
import json
import os
from pathlib import Path

from ls_satsearch.run import read_csv,sha,write_json
from scripts.v14_C_shard_accept import run as accept


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Saved-member validation requires Slurm')
    states=[]
    for cohort in ('south_outside_census','south_outside_census_extension'):
        source=Path('results/v14/discovery')/cohort/'main/sky_group_candidates.csv'
        for index in range(8):
            directory=Path('results/v14/candidate_review/v14')/cohort/f'{index:02d}'
            record=dict(cohort=cohort,index=index,directory=str(directory))
            try:
                if not (directory/'provenance.json').is_file():
                    selection=directory/'review_modes.csv'
                    if source.is_file() and selection.is_file() and not read_csv(selection):
                        record.update(state='no_selected_modes',source_sha256=sha(source),selection_sha256=sha(selection))
                    else:record.update(state='missing_provenance')
                else:
                    accept(directory)
                    proof=directory/'acceptance.json';m=json.loads(proof.read_text())
                    record.update(state='accepted_complete' if m['all_selected_C_fits_complete'] else 'terminal_incomplete_fits',
                                  proof_sha256=sha(proof),groups=m['exact_source_groups'],seeds=m['selected_seeds'],
                                  fit_states=m['fit_states'])
            except Exception as error:
                record.update(state='failed_acceptance',error_type=type(error).__name__,error=str(error))
            states.append(record)
    failed=[r for r in states if r['state'] not in ('accepted_complete','no_selected_modes')]
    out=Path('results/v14/production_integration/checkpoints/outside_C_final_20261120/acceptance.json')
    write_json(out,dict(job=os.environ['SLURM_JOB_ID'],runner_sha256=sha(Path(__file__)),shards=states,
        all_selected_C_accepted=not failed,failed_shards=len(failed),final_production_frozen=False,
        scope='Exact completed-source/configuration/discovery-seed/saved-membership validation. Missing computation and terminal unavailable fits stay explicit; no fit, retry, discovery, classification or image-QA performed. Final common-clock production/area/human evidence remain separate.'))
    print('Accepted outside C shards:',len(states)-len(failed),'/',len(states))
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
