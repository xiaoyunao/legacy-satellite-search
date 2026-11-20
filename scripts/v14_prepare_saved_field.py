"""Prepare a registered saved-C field privately, without fitting or grading.

The same renderers are used for ordinary candidates and weak known controls.
Names/truth metadata stay out of phase-one panels and any future alias key.
"""
import argparse
import json
import os
from pathlib import Path

from ls_satsearch.data import load_bricks,select
from ls_satsearch.run import field_cache,read_csv,sha,write_json
from ls_satsearch.search import load_isochrone
from scripts.v14_catalog import bound_fit_seed
from scripts.v14_phase1_panels import render as phase1
from scripts.v14_phase1_extent import render as extent
from scripts.v14_saved_context import render_mode

PLAN=Path('configs/v14_review_preparation/weak_controls.json')


def run(index):
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Slurm is required')
    plan=json.loads(PLAN.read_text())
    for name,digest in plan['input_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Registered control source changed: '+name)
    spec=plan['fields'][index]
    data=Path(os.environ['LS_SAT_DATA']);root=Path(os.environ['LS_DR11_ROOT'])
    manifest=Path(spec['scan_manifest']);saved=json.loads(manifest.read_text())
    if saved['status']!='complete' or saved['field']['id']!=spec['field'] or saved['depth']!='base':
        raise ValueError('Original complete baseline scan required')
    cfg=saved['config'];model_path=data/'resources'/cfg['isochrone']
    if sha(model_path)!=saved['model_sha256']:raise ValueError('Original template changed')
    groups=set(spec['group_ids'])
    seeds=[r for r in read_csv(Path(spec['seeds'])) if r['group_id'] in groups
           and r['policy']=='A_base' and float(r['budget'])==.3]
    modes=[r for r in read_csv(Path(spec['fits'])) if r['candidate_group_id'] in groups]
    expected={(r['group_id'],int(float(r['peak_rank']))) for r in seeds}
    if ({(r['candidate_group_id'],int(float(r['rank']))) for r in modes}!=expected or
            len(modes)!=len(expected) or any(r['fit_status']!='complete' for r in modes)):
        raise ValueError('All original retained control modes must be complete')
    region=cfg.get('region','south');bricks=load_bricks(root,region)
    field,sources,area,_=field_cache(root,data,saved['field'],cfg,bricks)
    sample,_,valid,mags,chosen=select(sources,field,area,cfg)
    model=load_isochrone(model_path)
    raw=data/spec['raw_template_peaks']
    output=Path('results/v14/human_review/final_private/saved_controls')/spec['control_id']/os.environ['SLURM_JOB_ID']
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    for i,mode in enumerate(sorted(modes,key=lambda r:(float(r['fit_dm']),float(r['fit_rh_arcmin']),float(r['fit_ra_deg']),float(r['fit_dec_deg'])))):
        rank=int(float(mode['rank']));group=mode['candidate_group_id']
        original=[r for r in seeds if r['group_id']==group]
        if not bound_fit_seed(mode,original):raise ValueError('C row belongs to another source seed')
        seed=next(r for r in original if int(float(r['peak_rank']))==rank)
        membership=data/(mode.get('membership_data_path') or
                         f"runs/{spec['run_version']}/{spec['field']}-base/membership-main-A-{rank}.npz")
        if mode.get('membership_sha256') and sha(membership)!=mode['membership_sha256']:
            raise ValueError('Original member source changed')
        dest=output/f'alternative_{i+1:02d}'
        render_mode(dest,mode,seed,membership,raw,field,area,sample,sources,valid,mags,chosen,
                    model,saved['field'],saved['observing_conditions_source_sample'],root,region,bricks)
        panel=phase1(dest/'phase1.png',f'Observed field / alternative {i+1:02d}',
                     sample,area,field,model[0],mode,root,region,bricks)
        wide=extent(dest/'phase1_extent.png',sample,area,field,mode,root,region,bricks)
        if panel['probabilities_or_scores_rendered'] or wide['probabilities_or_scores_rendered']:
            raise ValueError('Anonymous evidence information policy failed')
        context=json.loads((dest/'manifest.json').read_text())
        records.append(dict(group_id=group,seed_rank=rank,context_manifest=str(dest/'manifest.json'),
            phase1_path=str(dest/'phase1.png'),extent_path=str(dest/'phase1_extent.png'),
            phase1_status=panel,extent_status=wide,membership_sha256=sha(membership),
            membership_integrity=context['membership_integrity'],
            centre_image_complete=context['image_centre_complete'],missing_member_stamps=context['image_missed_member_stamps']))
    proof=dict(job=os.environ['SLURM_JOB_ID'],control_id=spec['control_id'],modes=len(modes),
        groups=len(groups),plan_sha256=sha(PLAN),scan_manifest_sha256=sha(manifest),
        raw_template_peaks_sha256=sha(raw),template_sha256=sha(model_path),
        outputs={str(p):sha(p) for p in output.rglob('*') if p.is_file()},mode_status=records,
        original_scan_config=cfg,refitted=False,human_grades_filled=False,
        production_discovery=False,final_review_release=False,
        scope='Private preparation of all saved ordinary-blind-discovery modes for a known weak control. No true centre/distance/member list supplied to any detector, no new detector or fit, no new system/independent confirmation, final sampling or human grading.')
    write_json(output/'acceptance.json',proof)
    print(json.dumps(dict(control_id=spec['control_id'],modes=len(modes),private_evidence_prepared=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('index',type=int)
    run(parser.parse_args().index)
