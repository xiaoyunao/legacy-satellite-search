"""Validate paired formal-depth replays; keep legacy and physical PS1 separate."""
import argparse
import json
import os
from pathlib import Path
import shutil

import numpy as np
import yaml

from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v14_repeat_statistics import interval,resample,simultaneous_paired_bound

ROOT=Path('results/v14/repeat_full/production_deeper_replay')
BASE=ROOT.with_name('production_replay')
METRICS=('spatial','blind_correct','correct_mode_exists','correct_mode_in_any_spatial_group')


def run(full=False):
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Validate source products on Slurm')
    completion=ROOT/('completion.json' if full else 'pilot_completion.json')
    done=json.loads(completion.read_text());registration=ROOT/'registration.json'
    if done['full144']!=full or done['registration_sha256']!=sha(registration):
        raise ValueError('Replay completion/registration differs')
    original=json.loads((BASE/'completion.json').read_text())
    if not original['all_registered_baseline_replays_complete']:
        raise ValueError('Accepted formal baseline required')
    inputs={str(p):sha(p) for p in (completion,registration,BASE/'completion.json',BASE/'registration.json',BASE/'statistics/acceptance.json')}
    left=json.loads((BASE/'registration.json').read_text());right=json.loads(registration.read_text())
    differences={k for k in set(left['configuration'])|set(right['configuration']) if left['configuration'].get(k)!=right['configuration'].get(k)}
    if differences!={'g_max','r_max'} or (left['width_deg'],left['buffer_arcmin'])!=(right['width_deg'],right['buffer_arcmin']):
        raise ValueError('Only registered magnitude limits may change the formal configuration')
    if left['cutoff']!=6.137901371660258 or right['cutoff']!=7.520695022636638:
        raise ValueError('Use the original frozen equal-budget cutoffs')
    inputs.update(original['source_sha256']);inputs.update(done['source_sha256']);inputs.update(right['source_sha256'])
    expected=set(range(48 if full else 6));pairs=[];blank=[]
    for site in (f'v14_south_response_{i}' for i in (1,2,3)):
        old_meta=json.loads((BASE/(site+'.json')).read_text())
        meta=json.loads((ROOT/(site+'.json')).read_text())
        old={int(r['trial']):r for r in read_csv(BASE/(site+'.csv'))}
        new=read_csv(ROOT/(site+'.csv'))
        if {int(r['trial']) for r in new}!=expected or len(new)!=len(expected):raise ValueError('Trial roster differs')
        if old_meta['field']!=meta['field'] or old_meta['real_mask_inputs']!=meta['real_mask_inputs']:
            raise ValueError('Formal core/actual mask inputs differ between depths')
        for code in ('src/ls_satsearch/search.py','src/ls_satsearch/group_budget.py'):
            if old_meta['source_code_sha256'][code]!=meta['source_code_sha256'][code]:
                raise ValueError('Discovery engine changed between paired arms')
        inputs.update(meta['input_sha256']);inputs.update(meta['source_code_sha256'])
        for r in new:
            b=old[int(r['trial'])]
            for key in ('site','trial','D_kpc','rh_pc','target_MV_proxy','realized_MV_proxy','latent_population_id','realization_id','N_exposed'):
                if r[key]!=b[key]:raise ValueError('Shared native population/exposure changed: '+key)
            if r['arm']!='production_ls_deep' or int(r['N_used'])<int(b['N_used']):
                raise ValueError('Deeper arm/monotone hard selection failed')
            if r['C_state']!='not_run_for_production_replay_do_not_reuse_matched_C':raise ValueError('Borrowed C evidence')
            row={k:r[k] for k in ('site','trial','D_kpc','rh_pc','target_MV_proxy','realized_MV_proxy','latent_population_id','realization_id','N_exposed')}
            row.update(baseline_N_used=b['N_used'],deeper_N_used=r['N_used'])
            for metric in METRICS:
                if r[metric] not in ('True','False') or b[metric] not in ('True','False'):raise ValueError('Missing actual response')
                row['baseline_'+metric]=b[metric];row['deeper_'+metric]=r[metric]
            pairs.append(row)
        blank.append(dict(site=site,baseline_qualifying_groups=old_meta['blank_qualifying_sky_groups'],
            deeper_qualifying_groups=meta['blank_qualifying_sky_groups']))
    model=Path(os.environ['LS_SAT_DATA'])/'resources'/right['configuration']['isochrone']
    accepted=json.loads((BASE/'statistics/acceptance.json').read_text())
    if accepted['input_sha256'].get(str(model))!=sha(model):raise ValueError('Physical stellar template differs')
    inputs[str(model)]=sha(model)
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Input changed: '+name)
    if not full:
        # The full run replaces its three live site summaries; preserve the
        # accepted pilot bytes and point its proof at those immutable copies.
        frozen=ROOT/'pilot_frozen';frozen.mkdir(exist_ok=True)
        for name in done['source_sha256']:
            source=Path(name);target=frozen/source.name
            if target.exists() and sha(target)!=sha(source):raise ValueError('Preserve earlier pilot bytes')
            if not target.exists():shutil.copy2(source,target)
            inputs[str(target)]=inputs.pop(name)
    write_csv(ROOT/('formal_depth_pairs.csv' if full else 'pilot_formal_depth_pairs.csv'),pairs)
    write_csv(ROOT/('blank_response.csv' if full else 'pilot_blank_response.csv'),blank)
    counts={metric:dict(baseline=sum(r['baseline_'+metric]=='True' for r in pairs),
        deeper=sum(r['deeper_'+metric]=='True' for r in pairs)) for metric in METRICS}
    if full:
        analysis_path=Path('configs/v14_repeat/analysis.yaml');analysis=yaml.safe_load(analysis_path.read_text())
        inputs[str(analysis_path)]=sha(analysis_path)
        inputs['scripts/v14_repeat_statistics.py']=sha(Path('scripts/v14_repeat_statistics.py'))
        cells=[(radius,mv) for radius in (3,10,30) for mv in (-3.,-1.5)]
        contrast=[];site_rates=[];sites=sorted({r['site'] for r in pairs})
        for metric in METRICS:
            delta=np.zeros((3,8,6),int);seen=set()
            for row in pairs:
                j=sites.index(row['site']);k=int(row['realization_id']);c=cells.index((float(row['rh_pc']),float(row['target_MV_proxy'])))
                if (j,k,c) in seen:raise ValueError('Duplicated background/population/cell')
                seen.add((j,k,c))
                delta[j,k,c]=int(row['deeper_'+metric]=='True')-int(row['baseline_'+metric]=='True')
            if len(seen)!=144:raise ValueError('Incomplete physical cell design')
            for site in sites:
                for radius,mv in cells:
                    rows=[r for r in pairs if r['site']==site and float(r['rh_pc'])==radius and float(r['target_MV_proxy'])==mv]
                    for arm in ('baseline','deeper'):
                        k=sum(r[arm+'_'+metric]=='True' for r in rows);low,high=interval(k,len(rows))
                        site_rates.append(dict(site=site,arm=arm,metric=metric,rh_pc=radius,target_MV_proxy=mv,
                            independent_IMF_draws=len(rows),detected=k,fraction=k/len(rows),
                            fixed_background_MC_low=low,fixed_background_MC_high=high,
                            realized_MV_proxy_min=min(float(r['realized_MV_proxy']) for r in rows),
                            realized_MV_proxy_max=max(float(r['realized_MV_proxy']) for r in rows)))
            draws=resample(delta,analysis['bootstrap_draws'],analysis['seed']);lo,hi=simultaneous_paired_bound(delta)
            for c in [None,*range(6)]:
                selection=slice(None) if c is None else slice(c,c+1);values=delta[:,:,selection]
                low,high=np.quantile(draws[:,selection].mean(axis=1),[.025,.975]);point=float(values.mean())
                contrast.append(dict(metric=metric,rh_pc='all' if c is None else cells[c][0],
                    target_MV_proxy='all' if c is None else cells[c][1],unique_populations=48 if c is None else 8,
                    backgrounds=3,background_trials=values.size,deeper_only=int((values==1).sum()),baseline_only=int((values==-1).sum()),
                    deeper_minus_baseline=point,resampling_p025=float(low),resampling_p975=float(high),
                    simultaneous_fixed_background_MC_low=float(lo[:,selection].mean()),
                    simultaneous_fixed_background_MC_high=float(hi[:,selection].mean()),
                    meets_registered_conditional_depth_screen=bool(point>.10 and low>0)))
        write_csv(ROOT/'paired_formal_depth_resampling.csv',contrast)
        write_csv(ROOT/'fixed_background_formal_depth_recovery.csv',site_rates)
    write_json(ROOT/('acceptance.json' if full else 'pilot_acceptance.json'),dict(
        accepted=True,job=os.environ['SLURM_JOB_ID'],registration_sha256=sha(registration),
        validated_paired_cases=len(pairs),shared_potential_populations=len(expected),backgrounds=3,
        same_formal_core_and_mask_verified=True,same_search_and_grouping_verified=True,
        hard_member_selection_monotone=True,counts=counts,
        usable_members=dict(baseline=sum(int(r['baseline_N_used']) for r in pairs),deeper=sum(int(r['deeper_N_used']) for r in pairs)),
        input_sha256=inputs,validator_sha256=sha(Path(__file__)),C_replayed=False,physical_PS1_response_validated=False,
        scope='Paired formal baseline/deeper A only, fixed existing equal-budget cuts and shared finite-rendered populations in three selected control interiors. Blank counts are three repeated skies, not144independent null trials. Registered crossed resampling/conservative bounds retain shared blocks, cells and skies; conditional depth screen is not all-sky confidence or physicalLSminusPS1gain. V-proxy/stamp/owned-edge/C/human/PS1limits remain.'))
    print('ACCEPTED_FORMAL_DEPTH_PAIRS',len(pairs),counts,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--full',action='store_true')
    run(parser.parse_args().full)
