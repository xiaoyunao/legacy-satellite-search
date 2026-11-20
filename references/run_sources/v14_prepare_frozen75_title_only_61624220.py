"""Prepare mandatory old-75 evidence privately while final production finishes.

No new human sample, grades, PDF release, C optimization or identity reveal.
"""
import argparse
import json
import os
from pathlib import Path
import numpy as np

from ls_satsearch.data import load_bricks, select
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_json
from ls_satsearch.search import load_isochrone
from scripts.v14_phase1_panels import render as render_phase1
from scripts.v14_saved_context import render_mode
from scripts.v14_phase1_extent import render as render_extent
from scripts.v14_review_integrity import mode_table

BASE = Path('results/v14/shortlist')
OUT = Path('results/v14/human_review/final_private/prepared75')


def prepare(index):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Evidence rendering requires Slurm')
    cases = read_csv(BASE/'cases.csv')
    if len(cases) != 75:
        raise ValueError('Original mandatory cases changed')
    case = cases[index]
    registration = json.loads((BASE/'manifest.json').read_text())
    if any(sha(Path(p)) != d for p,d in registration['packet_hashes'].items()):
        raise ValueError('Frozen old-75 input changed')
    final = OUT/case['case_id']/'accepted.json'
    accepted = None
    if final.is_file():
        accepted = json.loads(final.read_text())
        if any(sha(Path(p)) != d for p,d in accepted['outputs'].items()):
            raise ValueError('Previously accepted private evidence changed')
        if (all('extent_status' in r for r in accepted['mode_status']) and
                accepted.get('phase1_renderer_sha256') == sha(Path('scripts/v14_phase1_panels.py'))):
            print('Already prepared mandatory case',index)
            return
    attempt = OUT/case['case_id']/os.environ['SLURM_JOB_ID']
    attempt.mkdir(parents=True,exist_ok=False)
    table,modes = mode_table(case)
    if accepted and sha(table) != accepted['mode_table_sha256']:
        raise ValueError('Accepted context mode table changed')
    config = Path('configs/v14/cohorts')/case['cohort']
    os.environ['LS_SAT_CONFIG_DIR'] = str(config)
    root,data,cfg = settings()
    region = cfg.get('region','south')
    manifest = Path(f'regional_v14_{case["cohort"]}/results/summary/{case["field"]}-base/manifest.json')
    saved = json.loads(manifest.read_text())
    template = data/'resources'/cfg['isochrone']
    if saved['config'] != cfg or saved['model_sha256'] != sha(template):
        raise ValueError('Original scan configuration/template differs')
    bricks = load_bricks(root,region)
    field,sources,area,_ = field_cache(root,data,saved['field'],cfg,bricks)
    sample,_,valid,mags,chosen = select(sources,field,area,cfg)
    model = load_isochrone(template)
    integrity = Path('results/v14/human_review/membership_integrity.json')
    frozen = json.loads(integrity.read_text())
    if sha(integrity.with_suffix('.csv')) != frozen['csv_sha256']:
        raise ValueError('Frozen membership proof changed')
    snapshots = {(r['case_id'],int(r['seed_rank'])):r for r in read_csv(integrity.with_suffix('.csv'))}
    seeds = read_csv(BASE/f'input_modes_{case["cohort"]}.csv')
    raw = data/'runs/v14'/f'{case["field"]}-base/all_template_peaks.csv'
    outputs,records = dict(accepted['outputs']) if accepted else {},[]
    old_modes = {int(r['seed_rank']):r for r in accepted['mode_status']} if accepted else {}
    for i,mode in enumerate(sorted(modes,key=lambda m:(float(m['fit_dm']),float(m['fit_rh_arcmin']),float(m['fit_ra_deg']),float(m['fit_dec_deg'])))):
        rank = int(float(mode['rank']))
        snapshot = snapshots[(case['case_id'],rank)]
        membership = data/snapshot['frozen_path']
        if sha(membership) != snapshot['membership_sha256']:
            raise ValueError('Frozen saved membership changed')
        seed = next(r for r in seeds if r['group_id']==case['source_group_id'] and int(float(r['peak_rank']))==rank)
        dest = attempt/f'alternative_{i+1:02d}'
        if accepted:
            # Reuse verified context; preserve every previous raster/proof unchanged.
            record = dict(old_modes[rank])
            dest.mkdir(parents=True)
        else:
            render_mode(dest,mode,seed,membership,raw,field,area,sample,sources,valid,mags,chosen,model,
                        saved['field'],saved['observing_conditions_source_sample'],root,region,bricks)
            record = dict(seed_rank=rank,context_manifest=str(dest/'manifest.json'))
        status = render_phase1(dest/'phase1.png',f'Observed field / alternative {i+1:02d}',
                              sample,area,field,model[0],mode,root,region,bricks)
        if status['probabilities_or_scores_rendered']:
            raise ValueError('Phase-one information policy failed')
        write_json(dest/'phase1_status.json',status)
        record.update(phase1_status=status,phase1_path=str(dest/'phase1.png'))
        if accepted and record.get('extent_status',{}).get('renderer_sha256') == sha(Path('scripts/v14_phase1_extent.py')):
            pass  # Existing full-extent pixels and radial data already have bound hashes.
        else:
            extent = render_extent(dest/'phase1_extent.png',sample,area,field,mode,root,region,bricks)
            write_json(dest/'phase1_extent_status.json',extent)
            record.update(extent_status=extent,extent_path=str(dest/'phase1_extent.png'))
        records.append(record)
    for p in attempt.rglob('*'):
        if p.is_file(): outputs[str(p)] = sha(p)
    proof = dict(job=os.environ['SLURM_JOB_ID'],case_id=case['case_id'],modes=len(modes),
        runner_sha256=sha(Path(__file__)), phase1_renderer_sha256=sha(Path('scripts/v14_phase1_panels.py')), mode_table_sha256=sha(table), source_manifest_sha256=sha(manifest),
        original_registration_sha256=sha(BASE/'manifest.json'), outputs=outputs,mode_status=records,
        previously_exposed_case=True,refitted=False,final_review_release=False,
        scope='Private preparation of mandatory frozen positions; no final sample draw or human grades. '
              'All retained saved modes, score-hidden unweighted phase one and held full context. '
              'Image coverage, privacy and full-page QA remain explicit final-release gates.')
    if accepted:
        archive = final.with_name('accepted_without_full_extent.json')
        if not archive.exists():archive.write_bytes(final.read_bytes())
        proof['previous_acceptance_sha256'] = sha(final)
    write_json(final,proof)
    print(json.dumps(dict(index=index,modes=len(modes),private_evidence_prepared=True)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('index',type=int)
    prepare(p.parse_args().index)
