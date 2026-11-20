"""Copy final verified review archives into the actual personal project quota."""
import argparse
from datetime import datetime,timezone
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def digest(path):
    with path.open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def archive(quota_receipt=None):
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Use allocated CPU resources for archive verification')
    private=Path('results/v14/human_review/final_private')
    release=Path(os.environ['PSCRATCH'])/'legacy-satellite-search/runs/v14/human_review/final_private/final_release_v1'
    package=release/'phase1';manifest=json.loads((package/'package_manifest.json').read_text())
    held=json.loads((release/'held_archive.json').read_text())
    if manifest['pilot'] or not manifest['final_ready_for_human_review']:
        raise ValueError('Require finalized nonpilot anonymous package')
    if (digest(package/'anonymous_review.zip')!=manifest['zip_sha256']
            or digest(release/'held_context.zip')!=held['archive_sha256']):
        raise ValueError('Verified archive bytes changed')
    sources={'anonymous_review.zip':package/'anonymous_review.zip',
        'held_context.zip':release/'held_context.zip',
        'package_manifest.json':package/'package_manifest.json',
        'phase1_package_manifest.preQA.json':package/'package_manifest.preQA.json',
        'held_archive.json':release/'held_archive.json'}
    for name in ('registration.json','anonymous_plan.json','held_context_key.json'):
        sources['assembly_'+name]=private/'final_assembly'/name
    for name in ('registration.json','selection.json','selected.csv','allocation.csv','frame.csv'):
        sources['population_'+name]=private/'final_population'/name
    for folder in ('phase1_page_QA','held_context_page_QA','held_environment_page_QA'):
        for name in ('render_QA.json','visual_QA.json','visual_worklog.json'):
            path=release/folder/name
            if path.exists():sources[folder+'_'+name]=path
    sources['phase1_structural_QA.json']=package/'structural_QA.json'
    sources['held_structural_QA.json']=release/'held_context/structural_QA.json'
    target=private/'final_archive_v1'
    if target.exists():raise ValueError('Preserve existing durable archive and its receipt')
    if not target.resolve().is_relative_to(Path.home().resolve()):
        raise ValueError('Durable archive must be in the actual personal HOME project')
    if quota_receipt:
        observed=json.loads(quota_receipt.read_text())
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(observed['utc'])).total_seconds()
        if observed['source']!='actual_login_myquota' or not 0<=age<600:
            raise ValueError('Require a fresh actual login-node quota observation')
        used,limit=observed['used_bytes'],observed['quota_bytes']
        sources['home_quota_observation.json']=quota_receipt
    else:
        quota=subprocess.check_output(['myquota'],text=True)
        line=next(row for row in quota.splitlines() if row.split()[:1]==['home'])
        values=re.findall(r'([\d.]+)([GT]iB)',line);scale={'GiB':2**30,'TiB':2**40}
        used,limit=[float(number)*scale[unit] for number,unit in values[:2]]
    required=sum(path.stat().st_size for path in sources.values())
    if limit-used-required<256*2**20:raise ValueError('Insufficient actual HOME quota after 256MiB reserve')
    hashes={name:digest(path) for name,path in sources.items()};target.mkdir()
    for name,path in sources.items():
        temporary=target/(name+'.partial');shutil.copy2(path,temporary)
        if digest(temporary)!=hashes[name]:raise ValueError('Durable copy differs')
        temporary.rename(target/name)
    receipt=dict(job=os.environ['SLURM_JOB_ID'],artifacts=hashes,files=len(sources),bytes=required,
        all_copies_hash_verified=True,home_quota_remaining_estimate_bytes=limit-used-required,
        identity_revealed=False,human_grades_filled=False,code_sha256=digest(Path(__file__)),
        scope='Actual personal HOME durable copies of finalized anonymous and private held archives, frozen source key/frame and full QA proofs. Scratch is not the only copy. No raw catalogue/member arrays are copied locally or published.')
    (target/'archive_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(archive_files=len(sources),archive_bytes=required,all_copies_hash_verified=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--quota-receipt',type=Path)
    archive(parser.parse_args().quota_receipt)
