"""Run or verify one registered private material task without repeating accepted work."""
import argparse
import json
import os
from pathlib import Path

from ls_satsearch.run import sha
from scripts import v14_prepare_record as renderer


def run(plan,index):
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Allocated CPUs required')
    registration=json.loads(plan.read_text());spec=registration['fields'][index]
    for name,digest in registration['input_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Registered material source changed')
    accepted=Path('results/v14/human_review/final_private/prepared_records')/spec['record_key']/'accepted.json'
    if accepted.exists():
        proof=json.loads(accepted.read_text());original=proof['source_spec']
        if (proof['source_detection_id']!=spec['source_detection_id'] or
                proof['scan_manifest_sha256']!=sha(Path(spec['scan_manifest'])) or
                proof['source_input_sha256'][original['fits']]!=sha(Path(spec['fits']))):
            raise ValueError('Existing preparation belongs to another original source')
        for name,digest in proof['outputs'].items():
            if sha(Path(name))!=digest:raise ValueError('Accepted evidence changed')
        data=Path(os.environ['LS_SAT_DATA'])
        for mode in proof['mode_status']:
            if (not mode['centre_image_complete'] or mode['missing_member_stamps'] or
                    sha(data/mode['membership_data_path'])!=mode['membership_sha256']):
                raise ValueError('Accepted source membership or evidence incomplete')
        print(dict(task=index,existing_preparation_verified=True,modes=proof['modes']),flush=True)
        return
    from scripts.v14_reuse_frozen_record import reuse
    if reuse(spec,plan,registration):
        run(plan,index)
        return
    renderer.PLAN=plan;renderer.run(index)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--index',type=int)
    args=parser.parse_args();index=args.index if args.index is not None else int(os.environ['SLURM_ARRAY_TASK_ID'])
    run(args.plan,index)
