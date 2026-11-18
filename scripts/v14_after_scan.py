"""Chain regional snapshots and review to completed Slurm arrays."""
import json
from pathlib import Path
import subprocess

from ls_satsearch.run import write_json


def submit(options, *, summary=False):
    base = ['sbatch','--parsable','-A','desi','-q','regular','-C','cpu','-N1',
            '-n1','-c8', '--mem=100G' if summary else '--mem=18G',
            '-t','04:00:00' if summary else '01:30:00','-o','logs/%x-%j.log']
    return subprocess.check_output(base+options,text=True).strip().split(';')[0]


if __name__ == '__main__':
    pending = json.loads(Path('logs/v14-dispatch.json').read_text())
    key = Path('logs/v14-followup.json')
    jobs = json.loads(key.read_text()) if key.is_file() else {}
    for cohort, scans in pending.items():
        latest = scans[-1]['job']
        if jobs.get(cohort,{}).get('scan') == latest:
            continue
        aggregate = submit(['-J','ls14-sum-'+cohort,'--dependency=afterany:'+latest,
                            'scripts/v14_finalize.sh','regional',cohort], summary=True)
        review = submit(['-J','ls14-c-'+cohort,'--dependency=afterok:'+aggregate,
                         '--array=0-7%2','scripts/v14_review.sh','v14',cohort,'8'])
        jobs[cohort] = dict(scan=latest, aggregate=aggregate, review=review)
        write_json(key,jobs)
        print(cohort,latest,aggregate,review,flush=True)
    dependency = ':'.join(v['review'] for k,v in jobs.items() if k in pending)
    final = jobs.get('release', {})
    if final.get('depends') != dependency:
        release = submit(['-J','ls14-release','--dependency=afterany:'+dependency,
                          'scripts/v14_finalize.sh','snapshot'], summary=True)
        jobs['release'] = dict(depends=dependency, job=release)
        write_json(key,jobs)
        print('release',release,flush=True)
