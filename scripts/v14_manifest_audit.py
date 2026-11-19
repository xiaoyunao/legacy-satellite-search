"""Audit registered fields and completed CCD products without reading survey FITS."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run(out=Path('results/v14/progress_20261118')):
    out.mkdir(exist_ok=True,parents=True)
    fields,totals=[],[]
    for folder in sorted(Path('configs/v14/cohorts').iterdir()):
        path=folder/'fields.yaml'
        specs=yaml.safe_load(path.read_text())['fields']
        checksum=sha(path)
        cohort=[]
        for i,spec in enumerate(specs):
            manifest=Path(f'regional_v14_{folder.name}/results/summary/{spec["id"]}-base/manifest.json')
            m=json.loads(manifest.read_text()) if manifest.exists() else {}
            status=m.get('status','missing')
            if m and (m['field']!=spec or m['fields_sha256']!=checksum):
                raise ValueError(f'Field definition changed in {manifest}')
            if status=='complete':
                if not manifest.with_name('deduplicated_peaks.csv').is_file():
                    raise ValueError(f'Complete run lacks peaks {manifest}')
                if not (Path(os.environ['LS_SAT_DATA'])/m['owned_coverage_path']).is_file():
                    raise ValueError(f'Complete run lacks owned raster {manifest}')
            r=dict(cohort=folder.name,field=spec['id'],index=i,status=status,job=m.get('slurm_job_id'),
                   effective_deg2=m.get('area_deg2') if status=='complete' else None,
                   valid_mask_deg2=m.get('area_deg2'),
                   selected_search_sources=m.get('cutflow',{}).get('psf'),
                   terminal_area_state=('scan_completed' if status=='complete' else
                     'no_valid_owned_area' if status=='no_usable_gr' and not m.get('area_deg2') else
                     'positive_mask_empty_selected_catalogue' if status=='no_usable_gr' else 'not_terminal'),
                   raw_peaks=m.get('raw_peaks'),dedup_peaks=m.get('deduplicated_peaks'),
                   wall_seconds=m.get('wall_seconds'),manifest_sha256=sha(manifest) if m else None)
            fields.append(r);cohort.append(r)
        counts=Counter(r['status'] for r in cohort)
        totals.append(dict(cohort=folder.name,registered=len(specs),completed=counts['complete'],
                           no_usable_gr=counts['no_usable_gr'],prepared=counts['prepared'],missing=counts['missing'],
                           actual_effective_deg2=sum(r['effective_deg2'] or 0 for r in cohort),
                           raw_peaks=sum(r['raw_peaks'] or 0 for r in cohort),
                           dedup_peaks=sum(r['dedup_peaks'] or 0 for r in cohort)))
    native=[]
    data=Path(os.environ['LS_SAT_DATA'])
    for row in read_csv(Path('configs/v14/image_fields.csv')):
        site=row['field']
        stage=data/'image-v14'/site
        available={p.name for p in stage.glob('*') if any(p.glob('tractor/*/tractor-*.fits'))}
        path=Path(f'results/v14/image_response/{site}.json')
        m=json.loads(path.read_text()) if path.exists() else {}
        native.append(dict(site=site,cohort=row['cohort'],blank=int('blank' in available),
                           tractor_trials=sum(p.startswith('trial') for p in available),
                           measured_trials=m.get('measured_trials'),expected_trials=m.get('requested_trials'),
                           measurement_job=m.get('job'),manifest_sha256=sha(path) if m else None))
    write_csv(out/'fields.csv',fields);write_csv(out/'area_by_cohort.csv',totals)
    write_csv(out/'native_audit.csv',native)
    write_json(out/'manifest.json',dict(utc=datetime.now(timezone.utc).isoformat(),
          fields=len(fields),complete=sum(r['completed'] for r in totals),
          no_usable=sum(r['no_usable_gr'] for r in totals),
          no_usable_with_positive_valid_mask=sum(r['terminal_area_state']=='positive_mask_empty_selected_catalogue' for r in fields),
          excluded_no_usable_valid_mask_deg2=sum((r['valid_mask_deg2'] or 0) for r in fields if r['status']=='no_usable_gr'),
          native_complete_sites=sum(r['measured_trials']==8 and r['tractor_trials']==8 and r['blank'] for r in native)))
    for row in totals:
        print(row,flush=True)
    print('Native sites',native,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('results/v14/progress_20261118'))
    run(parser.parse_args().output)
