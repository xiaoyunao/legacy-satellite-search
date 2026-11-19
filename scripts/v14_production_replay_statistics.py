"""Accept and summarize the144 formal-baseline control replays, without borrowing C."""
import json
import os
from pathlib import Path

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_repeat_statistics import interval

ROOT=Path('results/v14/repeat_full/production_replay')
METRICS=('spatial','blind_correct','correct_mode_exists','correct_mode_in_any_spatial_group')


def run():
    completion=ROOT/'completion.json';done=json.loads(completion.read_text())
    if not done['all_registered_baseline_replays_complete'] or done['native_catalogue_replays']!=144:
        raise ValueError('Complete all registered baseline replays first')
    registration=ROOT/'registration.json'
    if done['registration_sha256']!=sha(registration):raise ValueError('Replay policy registration changed')
    sources={str(completion):sha(completion),str(registration):sha(registration)}
    legacy=ROOT.parent/'full_summary.csv';legacy_proof=ROOT.parent/'full_acceptance.json'
    if sha(legacy)!=json.loads(legacy_proof.read_text())['summary_sha256']:
        raise ValueError('Accepted legacy comparison changed')
    from scripts.v13_image_trials import template_paths
    model=template_paths(Path(os.environ['LS_SAT_DATA']),json.loads(registration.read_text())['configuration'])[0]
    if {r['model_sha256'] for r in read_csv(legacy)}!={sha(model)}:
        raise ValueError('Physical template differs from accepted legacy experiment')
    sources.update({str(p):sha(p) for p in (legacy,legacy_proof,model)})
    for name,digest in done['source_sha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Completed site changed: '+name)
        sources[name]=digest
    rows=[]
    for site in (f'v14_south_response_{i}' for i in (1,2,3)):
        meta=json.loads((ROOT/(site+'.json')).read_text())
        table=read_csv(ROOT/(site+'.csv'))
        if not meta['complete_registered_site'] or len(table)!=48 or {int(r['trial']) for r in table}!=set(range(48)):
            raise ValueError('Missing/duplicate registered control populations')
        for name,digest in meta['source_code_sha256'].items():
            if sha(Path(name))!=digest:raise ValueError('Replay implementation changed: '+name)
        for row in table:
            if row['site']!=site or row['C_state']!='not_run_for_production_replay_do_not_reuse_matched_C':
                raise ValueError('Unexpected site or transplanted C evidence')
            rows.append(row)
    for trial in range(48):
        shared=[r for r in rows if int(r['trial'])==trial]
        if len({tuple(r[k] for k in ('D_kpc','rh_pc','target_MV_proxy','realized_MV_proxy','latent_population_id','realization_id')) for r in shared})!=1:
            raise ValueError('Underlying shared population differs between backgrounds')
    per_background=[];pooled=[]
    for metric in METRICS:
        for rh,mv in [(None,None),*((r,m) for r in (3,10,30) for m in (-3,-1.5))]:
            selected=[r for r in rows if rh is None or (float(r['rh_pc'])==rh and float(r['target_MV_proxy'])==mv)]
            n=len(selected);success=sum(r[metric]=='True' for r in selected)
            old=sum(r['matched_'+metric]=='True' for r in selected)
            pooled.append(dict(metric=metric,rh_pc=rh if rh else 'all',target_MV_proxy=mv if rh else 'all',
                background_trials=n,unique_populations=n//3,production_detected=success,matched_detected=old,
                production_fraction=success/n,production_minus_matched_fraction=(success-old)/n,
                production_only=sum(r[metric]=='True' and r['matched_'+metric]!='True' for r in selected),
                matched_only=sum(r[metric]!='True' and r['matched_'+metric]=='True' for r in selected)))
            if rh is None:continue
            for site in sorted({r['site'] for r in selected}):
                cell=[r for r in selected if r['site']==site];k=sum(r[metric]=='True' for r in cell)
                if len(cell)!=8:raise ValueError('Unexpected fixed-background physical cell')
                low,high=interval(k,8)
                per_background.append(dict(site=site,metric=metric,rh_pc=rh,target_MV_proxy=mv,
                    independent_IMF_draws=8,detected=k,fraction=k/8,
                    fixed_background_MC_low=low,fixed_background_MC_high=high))
    out=ROOT/'statistics';out.mkdir(exist_ok=True)
    write_csv(out/'accepted_trials.csv',rows)
    write_csv(out/'policy_transfer_summary.csv',pooled)
    write_csv(out/'fixed_background_cell_recovery.csv',per_background)
    write_json(out/'acceptance.json',dict(input_sha256=sources,code_sha256=sha(Path(__file__)),
        accepted_formal_baseline_replays=144,unique_populations=48,backgrounds=3,
        C_replayed=False,physical_PS1_response_validated=False,
        scope='Frozen production-baseline A in three selected control interiors. Pooled fractions are descriptive; each fixed-background physical cell has eight independent IMF draws with exact marginal Monte Carlo intervals. The matched versus production difference changes grid, spatial trials, mask/context and cut together, not a causal single-setting effect. Shared populations, V-proxy luminosities, finite rendering/stamp, physical PS1 validation, owned-edge transfer and C/human review remain separate. No physical LS−PS1 gain, continuous completeness contour or population inference.'))
    print('ACCEPTED144_FORMAL_BASELINE_REPLAYS',flush=True)


if __name__=='__main__':run()
