"""Aggregate completed DR11 fields in a restartable snapshot and apply regional review policies."""
import argparse
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.group_budget import evaluate
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def frozen_policy(cohort):
    if cohort == 'south_ps1':
        return Path('configs/v7/production.json')
    if cohort in ('north','south_delve','south_des'):
        return Path(f'results/v11/{cohort}/main/calibration/sky_group_policy.json')
    return None


def run(only):
    root = Path('results/v14/discovery')
    root.mkdir(exist_ok=True, parents=True)
    samples = []
    for folder in sorted(Path('configs/v14/cohorts').glob('*')):
        cohort = folder.name
        if only and cohort not in only:
            continue
        fields_path = folder/'fields.yaml'
        fields = yaml.safe_load(fields_path.read_text())['fields']
        fields_sha = sha(fields_path)
        # Outside census, freeze the split from registration IDs, without
        # editing the original field manifests or using candidate outcomes.
        roles = {f['id']: ('pilot_dev' if i % 5 == 0 else 'pilot_eval')
                 for i, f in enumerate(fields)} if cohort == 'south_outside_census' else {}
        analysis_role = lambda f: roles.get(f['id'], f['role'])
        workspace = Path(f'regional_v14_{cohort}')
        output = root/cohort
        output.mkdir(exist_ok=True)
        rows = []
        complete = []
        for field in fields:
            parent = workspace/'results/summary'/f'{field["id"]}-base'
            path = parent/'manifest.json'
            m = json.loads(path.read_text()) if path.is_file() else {}
            if m and (m['fields_sha256'] != fields_sha or m['field'] != field):
                raise ValueError(f'Unexpected frozen input in {path}')
            cond = m.get('observing_conditions_source_sample',{})
            cutflow = m.get('cutflow',{})
            status = m.get('status','missing')
            if status == 'complete':
                complete.append((parent, field))
            rows.append(dict(field=field['id'], layer=field['layer'], role=analysis_role(field),
                         proxy_deg2=field['proxy_area_deg2'], status=status, job=m.get('slurm_job_id'),
                         valid_mask_deg2=m.get('area_deg2'),
                         background_core_deg2=m.get('background_core_deg2'),
                         searched_deg2=m['area_deg2'] if status=='complete' else None,
                         g_seeing=(cond.get('G',{}).get('seeing') or [None]*3)[1],
                         r_seeing=(cond.get('R',{}).get('seeing') or [None]*3)[1],
                         g_depth=(cond.get('G',{}).get('depth5_dered') or [None]*3)[1],
                         r_depth=(cond.get('R',{}).get('depth5_dered') or [None]*3)[1],
                         ebv=(cond.get('ebv') or [None]*3)[1],
                         psf=cutflow.get('inner_psf'), other=cutflow.get('inner_other'),
                         bright_mask_selected=cutflow.get('selected_maskbit_counts',{}).get('1'),
                         raw_peaks=m.get('raw_peaks'), dedup_peaks=m.get('deduplicated_peaks'),
                         seconds=m.get('wall_seconds'), manifest_sha256=sha(path) if m else None))
        write_csv(output/'fields.csv', rows)
        summary = dict(cohort=cohort, registered=len(fields), completed=len(complete),
                       no_usable=sum(r['status']=='no_usable_gr' for r in rows),
                       prepared=sum(r['status']=='prepared' for r in rows),
                       missing=sum(r['status']=='missing' for r in rows),
                       planned_proxy_deg2=sum(r['proxy_deg2'] for r in rows),
                       searched_deg2=sum(r['searched_deg2'] or 0 for r in rows),
                       valid_unsearched_mask_deg2=sum(r['valid_mask_deg2'] or 0 for r in rows if r['status']=='no_usable_gr'),
                       raw_peaks=sum(r['raw_peaks'] or 0 for r in rows), dedup_peaks=sum(r['dedup_peaks'] or 0 for r in rows))
        policy = frozen_policy(cohort)
        if not complete:
            samples.append(summary)
            continue
        archive = workspace/'release_snapshot'
        completed = archive/'all'
        completed.mkdir(exist_ok=True,parents=True)
        for p, f in complete:
            link = completed / p.name
            if not link.exists():
                link.symlink_to(p.resolve(),target_is_directory=True)
        if policy is None:
            stable = output/'calibration/sky_group_policy.json'
            development = [p for p,f in complete if analysis_role(f)=='pilot_dev']
            expected = sum(analysis_role(f)=='pilot_dev' for f in fields)
            ready = sum(r['role']=='pilot_dev' and r['status'] in ('complete','no_usable_gr') for r in rows)
            if not stable.exists() and ready == expected and development:
                cal = archive/'development'
                cal.mkdir(exist_ok=True)
                for p in development:
                    link = cal / p.name
                    if not link.exists():
                        link.symlink_to(p.resolve(),target_is_directory=True)
                evaluate(cal, stable.parent, channels_only=('A_base',), analysis_roles=roles)
            policy = stable if stable.exists() else None
        if policy:
            evaluate(completed, output/'main', apply=policy, channels_only=('A_base',), analysis_roles=roles)
            comparison = next(r for r in read_csv(output/'main/sky_group_comparison.csv') if r['budget']=='0.3')
            summary.update(primary_cut=comparison['cutoff'], primary_eval=comparison['evaluation_sky_groups'],
                           primary_dev=comparison['dev_sky_groups'], threshold_source=str(policy))
        else:
            summary['threshold_source'] = 'awaiting completed development scans'
        samples.append(summary)
    if only:
        write_csv(root/('status-'+'-'.join(only)+'.csv'), samples)
    else:
        write_csv(root/'status.csv', samples)
        config = Path('configs/v14/full_plan.yaml')
        write_json(root/'status.json', dict(job=os.getenv('SLURM_JOB_ID'), plan_sha256=sha(config), layers=samples,
                   note='Counts are per-field before combining duplicates between blocks. Exposure areas in the table come from completed manifests.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cohorts', nargs='*')
    run(p.parse_args().cohorts)
