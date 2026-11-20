"""Reuse original75 rasters only for an identical qualified source and saved fit."""
import argparse
from functools import cache
import json
import os
from pathlib import Path

from ls_satsearch.run import read_csv,sha,write_json
from scripts.v14_catalog import bound_fit_seed

ROOT=Path('results/v14/human_review/final_private')
KEYS=('fit_ra_deg','fit_dec_deg','fit_dm','fit_rh_arcmin','ts','richness','profile_integral',
      'bg_per_arcmin2','n_local','seed_dm','seed_rh_arcmin','C_refit_TS_without_top1',
      'C_refit_TS_without_top3','top1_membership_fraction','top3_membership_fraction',
      'effective_members','cmd_on_snr5','cmd_off_snr5','cmd_on_snr7','cmd_off_snr7')


@cache
def cases():
    return {f"results/v14/discovery/{r['cohort']}/main:{r['source_group_id']}":r
            for r in read_csv(Path('results/v14/shortlist/cases.csv'))}


@cache
def frozen_members():
    return {(r['case_id'],int(r['seed_rank'])):r
            for r in read_csv(Path('results/v14/human_review/membership_integrity.csv'))}


def reuse(spec,plan_path,plan):
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required for saved-source verification')
    case=cases().get(spec['source_detection_id'])
    if case is None:return False
    original=ROOT/'prepared75'/case['case_id']/'accepted.json';old=json.loads(original.read_text())
    if old['source_manifest_sha256']!=plan['input_sha256'][spec['scan_manifest']]:return False
    current=read_csv(Path(spec['fits']));saved={int(r['seed_rank']):r for r in old['mode_status']}
    if len(current)!=len(saved):return False
    seeds=[r for r in read_csv(Path(spec['seeds'])) if r['group_id'] in spec['group_ids']]
    linked=[]
    for row in current:
        status=saved.get(int(float(row['rank'])))
        if status is None:return False
        context=json.loads(Path(status['context_manifest']).read_text());mode=context['mode']
        try:equal=all(float(row[k])==float(mode[k]) for k in KEYS)
        except (KeyError,ValueError):return False
        if (not equal or row['candidate_group_id']!=mode['candidate_group_id'] or
                not bound_fit_seed(mode,seeds) or not bound_fit_seed(row,seeds)):return False
        linked.append((row,status,context))
    for name,digest in old['outputs'].items():
        if sha(Path(name))!=digest:raise ValueError('Preserved original75 evidence changed')
    data=Path(os.environ['LS_SAT_DATA']);manifest=Path(spec['scan_manifest']);source=json.loads(manifest.read_text())
    model=data/'resources'/source['config']['isochrone']
    if sha(model)!=source['model_sha256']:raise ValueError('Original model changed')
    modes=[]
    for row,status,context in linked:
        member=frozen_members()[case['case_id'],int(float(row['rank']))]
        if (member['membership_sha256']!=context['membership_sha256'] or
                sha(data/member['frozen_path'])!=context['membership_sha256'] or
                not context['membership_integrity']['verified'] or
                not context['image_centre_complete'] or context['image_missed_member_stamps']):
            raise ValueError('Original saved member/likelihood/native evidence failed')
        modes.append(dict(status,group_id=row['candidate_group_id'],membership_data_path=member['frozen_path'],
            membership_sha256=context['membership_sha256'],membership_integrity=context['membership_integrity'],
            centre_image_complete=context['image_centre_complete'],missing_member_stamps=context['image_missed_member_stamps']))
    dest=ROOT/'prepared_records'/spec['record_key'];dest.mkdir(parents=True,exist_ok=False)
    proof=dict(job=os.environ['SLURM_JOB_ID'],record_key=spec['record_key'],source_detection_id=spec['source_detection_id'],
        modes=len(modes),groups=len(spec['group_ids']),plan_sha256=sha(plan_path),
        scan_manifest_sha256=sha(manifest),raw_template_peaks_sha256=sha(data/spec['raw_template_peaks']),
        template_sha256=sha(model),outputs=old['outputs'],mode_status=modes,original_scan_config=source['config'],
        source_spec=spec,source_input_sha256=plan['input_sha256'],refitted=False,rerendered=False,
        reused_original75_proof=str(original),reused_original75_proof_sha256=sha(original),
        reuse_driver_sha256=sha(Path(__file__)),human_grades_filled=False,new_discovery=False,
        final_selection=False,final_review_release=False,
        scope='Exact same qualified R14 source/group, original scan/model, every retained seed and all20scientific C fields agree with preserved original75. Frozen member bytes/likelihood and native image proofs verified. Reuse original rasters without fitting or rendering; preserve both source origins. No position-only C borrowing, new draw, grade or evidence promotion.')
    write_json(dest/'accepted.json',proof)
    return True


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args();plan=json.loads(args.plan.read_text())
    for name,digest in plan['input_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Registered source changed')
    counts=dict(reused_records=0,reused_modes=0)
    for spec in plan['fields']:
        if (ROOT/'prepared_records'/spec['record_key']/'accepted.json').exists():continue
        if reuse(spec,args.plan,plan):
            counts['reused_records']+=1;counts['reused_modes']+=len(read_csv(Path(spec['fits'])))
    print(counts,flush=True)
