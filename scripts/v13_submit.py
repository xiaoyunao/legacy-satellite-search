"""Submit downloaded fields and chain physical trials to their matched scan."""
import json
import os
import subprocess
from pathlib import Path

from ls_satsearch.run import read_csv, write_json


def queue(opts):
    base = ['sbatch', '--parsable', '-A', 'desi', '-q', 'regular', '-C', 'cpu',
            '-N1', '-n1', '-c4', '-o', 'logs/%x-%j.log']
    return subprocess.check_output(base+opts, text=True).strip().split(';')[0]


def run():
    data = Path(os.environ['PSCRATCH'])/'legacy-satellite-search/resources/ps1/tiles-v3'
    path = Path('logs/v13-submitted.json')
    jobs = json.loads(path.read_text()) if path.exists() else {}
    for row in read_csv(Path('configs/v13/matched/strata.csv')):
        field, region = row['field'], row['region']
        if not (data/field/'manifest.json').is_file():
            continue
        match = 'matched/'+field
        environment = '--export=ALL,LS_SAT_VERSION=v13,LS_SAT_PROFILE=matched/'+region
        if match not in jobs:
            jobs[match] = queue([environment, '-t','00:40:00','--mem=14G','-J','ls13-match-'+field,
                                 'scripts/v12_matched.sh',region,field])
            write_json(path,jobs)
        trial = 'trials/'+field
        if trial not in jobs:
            command = (f'bash scripts/v6.sh response_trials {field} --version v13 '
                       f'--archive matched_v13_{region}/results/matched '
                       f'--policy-archive results/v12/matched/{region} '
                       f'--physical-plan configs/v13/physical_trials.yaml '
                       f'--output results/v13/selection_trials/{region}')
            jobs[trial] = queue([environment, '-t','02:00:00','--mem=13G','-J','ls13-trial-'+field,
                                 '--dependency=afterok:'+jobs[match],'--kill-on-invalid-dep=yes',
                                 '--wrap',command])
            write_json(path,jobs)
    print(jobs)


if __name__ == '__main__':
    run()
