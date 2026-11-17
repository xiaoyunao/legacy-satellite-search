"""Aggregate frozen paired trials, recording background-level variation and held-out load."""
from collections import defaultdict
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.group_budget import evaluate
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from v12_selection_stats import interval, summarize
from v12_review_stats import save

RESULTS = Path('results/v13')
SURVEYS=('ls_base','ls_deep','ps1')
STAGES=('N_latent','N_in_valid_area','N_valid_gr','N_used','N_CMD','N_CMD_on',
        'background_CMD_on','background_CMD_off','truth_center_score_blank',
        'truth_center_score_injected','spatial','correct_mode_exists','blind_correct','blank_spatial')


def value(row, key):
    return float({'True':1, 'False':0}.get(row[key],row[key])) if row.get(key) else np.nan


def pair_stats(bucket, scope, metric):
    n=len(bucket)
    for a,b in (('ls_base','ps1'),('ls_deep','ps1'),('ls_deep','ls_base')):
        first=np.array([r[a][metric]=='True' for r in bucket])
        second=np.array([r[b][metric]=='True' for r in bucket])
        wins=int((first&~second).sum())
        losses=int((~first&second).sum())
        lo_w,hi_w=interval(wins,n,.975)
        lo_l,hi_l=interval(losses,n,.975)
        yield dict(scope=scope,metric=metric,first=a,second=b,first_pass=first.sum(),second_pass=second.sum(),
                   trials=n,wins=wins,losses=losses,difference=(wins-losses)/n,lower=lo_w-hi_l,upper=hi_w-lo_l)


def main():
    strata=read_csv(Path('configs/v13/matched/strata.csv'))
    results={}
    provenance=[]
    load=[]
    for spec in strata:
        region,field=spec['region'],spec['field']
        p=RESULTS/'selection_trials'/region/f'{field}.csv'
        manifest=p.with_suffix('.json')
        m=json.loads(manifest.read_text())
        if m['status']!='complete':
            raise ValueError(f'No completed result for {field}')
        provenance.append(dict(field=field,trial_manifest_sha256=sha(manifest),job=m['job'],rows_sha256=sha(p)))
        table=read_csv(p)
        bucket=defaultdict(dict)
        for row in table:
            bucket[int(row['trial'])][row['survey']]=dict(row,version='v13',stratum=spec['stratum'])
        if len(bucket)!=len(m['physical_plan']['conditions']) or any(set(r)!=set(SURVEYS) for r in bucket.values()):
            raise ValueError(f'Incomplete physical pairing in {field}')
        results[field]=bucket
    out=RESULTS/'selection'
    out.mkdir(exist_ok=True,parents=True)
    entries=[r for b in results.values() for trial in b.values() for r in trial.values()]
    summarize(entries,out)

    comparisons=[]
    summaries=[]
    for spec in strata:
        field=spec['field']
        trials=list(results[field].values())
        for metric in ('spatial','correct_mode_exists','blind_correct'):
            comparisons.extend(pair_stats(trials,field,metric))
        for survey in SURVEYS:
            for distance in (100,150):
                subset=[t[survey] for t in trials if int(t[survey]['D_kpc'])==distance]
                summaries.append(dict(**spec,survey=survey,D_kpc=distance,n=len(subset),
                                      **{k:np.nansum([value(r,k) for r in subset]) for k in STAGES[:9]},
                                      **{k:int(sum(r[k]=='True' for r in subset)) for k in STAGES[-4:]}))
    for region in ('north','south'):
        group=[v for f,t in results.items() if next(r for r in strata if r['field']==f)['region']==region
               for v in t.values()]
        for d in (None,100,150):
            chunk=[t for t in group if d is None or int(t['ls_base']['D_kpc'])==d]
            for metric in ('spatial','correct_mode_exists','blind_correct'):
                comparisons.extend(pair_stats(chunk,region if d is None else f'{region}_{d}',metric))
        for survey in SURVEYS:
            archive=Path(f'matched_v13_{region}/results/matched')/survey/'summary'
            target=out/'heldout'/region/survey
            policy=Path(f'results/v12/matched/{region}/{survey}/groups/sky_group_policy.json')
            evaluate(archive,target,apply=policy,channels_only=('A_base',))
            load.extend(dict(region=region,survey=survey,policy_sha256=sha(policy),**r)
                        for r in read_csv(target/'sky_group_comparison.csv'))
    matched=[]
    for pair in sorted({s['stratum'] for s in strata if s['stratum'].startswith('pair')}):
        south=next(s['field'] for s in strata if s['stratum']==pair and s['region']=='south')
        north=next(s['field'] for s in strata if s['stratum']==pair and s['region']=='north')
        for trial,arms in results[south].items():
            other=results[north][trial]
            for survey,row in arms.items():
                nr=other[survey]
                shared=('N_latent','N_imf_drawn','expected_MV_proxy','D_kpc','rh_pc')
                if any(row[k]!=nr[k] for k in shared) or not np.isclose(
                        float(row['actual_MV_proxy']),float(nr['actual_MV_proxy']),atol=1e-10,rtol=0):
                    raise ValueError(f'Shared stellar draw differs for {pair}/{trial}/{survey}')
                matched.append(dict(pair=pair,trial=trial,south=south,north=north,survey=survey,
                                    **{k:row[k] for k in ('D_kpc','rh_pc','expected_MV_proxy')},
                                    **{f'south_{k}':row.get(k) for k in STAGES},
                                    **{f'north_{k}':nr.get(k) for k in STAGES}))
    write_csv(out/'paired_by_background.csv',comparisons)
    write_csv(out/'stage_by_background.csv',summaries)
    write_csv(out/'matched_north_south.csv',matched)
    write_csv(out/'heldout_review_cost.csv',load)
    write_json(out/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),inputs=provenance,
               scope='Paired exact binomial bounds are conditional on sampled backgrounds; '
               'field stability is reported separately. Joint DR11 source-entry response remains '
               'a separate image-based experiment.'))

    fig,axes=plt.subplots(1,2,figsize=(10,4.9),sharex=True,layout='constrained')
    for axis,region in zip(axes,('south','north')):
        fields=[s['field'] for s in strata if s['region']==region]
        rows=[next(r for r in comparisons if r['scope']==f and r['first']=='ls_deep'
                   and r['second']=='ps1' and r['metric']=='spatial') for f in fields+[region]]
        values=np.array([r['difference'] for r in rows])
        axis.errorbar(values,np.arange(len(rows)),
                      xerr=[values-[r['lower'] for r in rows],[r['upper'] for r in rows]-values],
                      fmt='o',c='#315783',capsize=2)
        axis.set_yticks(np.arange(len(rows)),[next(s['stratum'] for s in strata if s['field']==r['scope']).replace('_',' ').replace('pair','Pair ')
                         if r['scope']!=region else 'All tested fields' for r in rows])
        axis.axvline(0,c='.6',lw=.8)
        axis.set(xlabel='LS deeper − PS1 DR2 spatial recovery',title=region.title())
    save(fig,out,'by_background')


if __name__ == '__main__':
    main()
