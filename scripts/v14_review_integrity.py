"""Bind each retained C table row to the actual saved membership on Slurm.

The point-process likelihood gives TS=2[-sum(log(1-p))-richness*integral].
This validates saved output without rerunning or optimizing a scientific fit.
Per-source arrays and immutable copies stay on NERSC scratch.
"""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv,sha,write_csv,write_json
from ls_satsearch.review import membership_path

ROOT=Path('results/v14/shortlist')


def verify(mode,ids,prob):
    if len(ids)!=len(prob) or len(prob)!=int(mode['n_local']):
        raise ValueError('Saved local-source count differs from C table')
    if len({tuple(k) for k in ids})!=len(ids):raise ValueError('Duplicate saved source identity')
    if not np.all(np.isfinite(prob)&(prob>=0)&(prob<1)):
        raise ValueError('Saved probabilities are invalid or too rounded for likelihood verification')
    expected=float(mode['richness'])*float(mode['profile_integral'])
    if not np.isclose(prob.sum(),expected,rtol=1e-6,atol=1e-6):
        raise ValueError('Saved membership sum differs from fitted richness normalization')
    ts=2*(-np.log1p(-prob).sum()-expected)
    if not np.isclose(ts,float(mode['ts']),rtol=1e-6,atol=1e-6):
        raise ValueError('Saved memberships do not reproduce the C likelihood')
    return dict(N_local=len(prob),probability_sum=float(prob.sum()),TS_reconstructed=float(ts),
                TS_stored=float(mode['ts']),verified=True)


def mode_table(case):
    wanted={int(float(r['peak_rank'])) for r in read_csv(ROOT/f'input_modes_{case["cohort"]}.csv')
            if r['group_id']==case['source_group_id']}
    for source in ('cases','cached_cases'):
        table=ROOT/source/case['case_id']/'review_modes.csv'
        if not table.is_file():continue
        modes=read_csv(table)
        if ({int(float(m['rank'])) for m in modes}==wanted and
            all(m['fit_status']=='complete' for m in modes)):
            return table,modes
    raise ValueError('Retained C packet is incomplete: '+case['case_id'])


def run(case_ids,output):
    manifest=json.loads((ROOT/'manifest.json').read_text())
    if any(sha(Path(name))!=value for name,value in manifest['packet_hashes'].items()):
        raise ValueError('Frozen case/mode packet changed before membership verification')
    cases=read_csv(ROOT/'cases.csv')
    if case_ids and not set(case_ids)<={r['case_id'] for r in cases}:raise ValueError('Unknown requested case ID')
    if case_ids:cases=[r for r in cases if r['case_id'] in case_ids]
    data=Path(os.environ['LS_SAT_DATA']);rows=[];tables={}
    frozen=data/'runs/v14/review_membership_frozen'/sha(ROOT/'manifest.json')[:12]
    previous_meta=output/'membership_integrity.json';previous_csv=output/'membership_integrity.csv'
    prior={};prior_tables={}
    if previous_meta.is_file() and previous_csv.is_file():
        previous=json.loads(previous_meta.read_text())
        if (previous.get('shortlist_manifest_sha256')==sha(ROOT/'manifest.json')
                and previous.get('csv_sha256')==sha(previous_csv)):
            prior={(r['case_id'],int(r['seed_rank'])):r for r in read_csv(previous_csv)}
            prior_tables=previous.get('table_hashes',{})
    for case in cases:
        table,modes=mode_table(case);tables[case['case_id']]=sha(table)
        for mode in modes:
            rank=int(float(mode['rank']))
            source=data/'runs/v14'/f'{case["field"]}-base'/f'membership-main-A-{rank}.npz'
            saved=prior.get((case['case_id'],rank))
            if not mode.get('membership_data_path') and saved and prior_tables.get(case['case_id'])==sha(table):
                source=data/saved['frozen_path']
                if sha(source)!=saved['membership_sha256']:raise ValueError('Previously frozen membership changed')
            source=membership_path(data,mode,source)
            raw=source.read_bytes();checksum=sha256(raw).hexdigest()
            with np.load(io.BytesIO(raw),allow_pickle=False) as members:
                proof=verify(mode,members['source_ids'],members['probability'])
            dest=frozen/case['case_id']/f'seed-{rank}-{checksum[:12]}.npz'
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():
                if sha(dest)!=checksum:raise ValueError('Frozen membership file changed')
            else:
                with dest.open('xb') as stream:stream.write(raw)
            rows.append(dict(case_id=case['case_id'],seed_rank=rank,**proof,
                membership_sha256=checksum,frozen_path=str(dest.relative_to(data))))
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'membership_integrity.csv',rows)
    write_json(output/'membership_integrity.json',dict(job=os.getenv('SLURM_JOB_ID'),
        csv_sha256=sha(output/'membership_integrity.csv'),
        positions=len(cases),modes=len(rows),all_registered_positions=(not case_ids and len(cases)==75),
        shortlist_manifest_sha256=sha(ROOT/'manifest.json'),table_hashes=tables,
        verification_code_sha256=sha(Path(__file__)),
        scope='Every included saved C membership reproduces local count, normalized richness and likelihood; immutable source arrays remain on NERSC scratch. This is output integrity, not a new fit, discovery or human scientific grade.'))
    print('Saved memberships verified:',len(cases),'positions,',len(rows),'modes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',default=[])
    parser.add_argument('--output',type=Path,default=Path('results/v14/human_review'))
    args=parser.parse_args();run(args.case,args.output)
