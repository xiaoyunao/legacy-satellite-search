"""Replay saved complete raw-template grids at the original and extended DM boundary."""

import argparse
import json
import os
from pathlib import Path

from ls_satsearch.group_budget import evaluate
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from ls_satsearch.search import deduplicate


NUMERIC = ('x', 'y', 'ra_deg', 'dec_deg', 'dm', 'rh_arcmin', 'score')


def replay(summary, raw_root, scratch, output, historical_south, apply_from):
    manifests = sorted(summary.glob('*/manifest.json'))
    if not manifests:
        raise ValueError(f'No manifests in {summary}')
    for dm_max, name in ((20.75, 'original'), (21.0, 'extended')):
        destination = scratch / name
        inputs = []
        for index, path in enumerate(manifests):
            m = json.loads(path.read_text())
            if m['status'] != 'complete' or m['depth'] != 'base':
                raise ValueError(f'Expected a complete baseline run at {path}')
            setting = m['config']['dm']
            if setting[0] > 16.5 or setting[1] < 21 or setting[2] != .25:
                raise ValueError(f'Raw grid did not cover both intervals at {path}')
            raw = raw_root / path.parent.name / 'all_template_peaks.csv'
            rows = read_csv(raw)
            if len(rows) != m['raw_peaks']:
                raise ValueError(f'Incomplete peak file {raw}')
            for row in rows:
                row.update({key: float(row[key]) for key in NUMERIC})
            peaks = deduplicate(rows, dm_max)
            if name == 'original':
                archived = read_csv(path.parent / 'deduplicated_peaks.csv')
                def keys(seq):
                    return [(r['branch'], int(r['rank']), int(r['raw_peak_id'])) for r in seq]
                if keys(peaks) != keys(archived):
                    raise ValueError(f'Historical merge mismatch for {path.parent.name}')
            field = m['field'].copy()
            if historical_south:
                field['role'] = 'pilot_dev' if index < len(manifests)//2 else 'pilot_eval'
            m['config']['main_dm_max'] = dm_max
            out = destination / path.parent.name
            out.mkdir(exist_ok=True, parents=True)
            write_json(out / 'manifest.json', dict(m, field=field))
            write_csv(out / 'deduplicated_peaks.csv', peaks)
            inputs.append(dict(field=field['id'], role=field['role'], original_manifest_sha256=sha(path),
                               raw_peaks_sha256=sha(raw), main_count=sum(p['branch']=='main' for p in peaks)))
        applied=apply_from/name/'sky_group_policy.json' if apply_from is not None else None
        evaluate(destination, output / name, archive=applied is None, apply=applied, channels_only=('A_base',))
        write_csv(output / name / 'inputs.csv', inputs)
        write_json(output / name / 'manifest.json', dict(job_id=os.getenv('SLURM_JOB_ID'),
                   main_dm_max=dm_max, method='full raw-template replay before distance-branch dedup',
                   validation='fresh frozen evaluation' if applied else
                   'archived fields used as regression, South split by field ID',
                   policy_sha256=sha(applied) if applied else None))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('summary', 'raw_root', 'scratch', 'output'):
        p.add_argument(arg, type=Path)
    p.add_argument('--historical-south', action='store_true')
    p.add_argument('--apply-from', type=Path)
    replay(**vars(p.parse_args()))
