"""Compare observed conditional recovery with the published census head-to-head treatments."""
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from v12_footprint import save
from v12_selection_stats import interval


def binned(rows, cohort, design):
    bins = defaultdict(list)
    for r in rows:
        arm = r.get('survey') or r['arm']
        bins[(arm, float(r['D_kpc']), float(r['rh_pc']), float(r['expected_MV_proxy']))].append(r)
    for (arm,d,rh,mv), entries in sorted(bins.items()):
        n = len(entries)
        backgrounds = {r.get('site') or r['field'] for r in entries}
        for key in ('spatial','correct_mode_exists','blind_correct','passes_C_stability_proxy'):
            qualified = [r for r in entries if r.get(key) in ('True','False')]
            if not qualified:
                continue
            count = sum(r[key]=='True' for r in qualified)
            lows, highs = interval(count,len(qualified))
            rates = [np.mean([r[key]=='True' for r in qualified if (r.get('site') or r['field']) == site])
                     for site in sorted(backgrounds)
                     if any((r.get('site') or r['field']) == site for r in qualified)]
            yield dict(cohort=cohort, design=design, survey=arm, D_kpc=d, rh_pc=rh, M_V_proxy=mv,
                       outcome=key, recovered=count, tested=n, with_outcome=len(qualified),
                       site_count=len(rates), fraction=count/len(qualified), low=lows, high=highs,
                       site_rate_min=min(rates),site_rate_max=max(rates))


def paired_backgrounds(rows, cohort):
    sources = defaultdict(dict)
    for r in rows:
        sources[r['field'],r['trial']][r['survey']] = r
    buckets = defaultdict(lambda: defaultdict(list))
    for (name,_),r in sources.items():
        if not {'ls_base','ls_deep','ps1'} <= r.keys():
            continue
        inherited = r['ls_base']
        for filters in (('all','all'),(inherited['D_kpc'],'all'),
                      (inherited['D_kpc'],inherited['rh_pc'])):
            for arm in ('ls_base','ls_deep'):
                for endpoint in ('spatial','correct_mode_exists','blind_correct'):
                    delta = int(r[arm][endpoint]=='True') - int(r['ps1'][endpoint]=='True')
                    buckets[arm,endpoint,*filters][name].append(delta)
    rng = np.random.default_rng(487146)
    for (arm,key,d,rh), fields in sorted(buckets.items()):
        values = np.array([np.mean(v) for v in fields.values()])
        if len(values)>1:
            draw = rng.choice(values,(10000,len(values))).mean(axis=1)
            low,high = np.quantile(draw,[.025,.975])
        else:
            low,high=None,None
        yield dict(cohort=cohort,first=arm,second='ps1_dr2',metric=key,D_kpc=d,rh_pc=rh,
                   backgrounds=len(values),trials=sum(map(len,fields.values())),
                   mean_with_equal_background_weights=values.mean(),
                   background_bootstrap_low=low,background_bootstrap_high=high,
                   background_min=values.min(),background_max=values.max())


def plot(outputs, data, image):
    color = dict(ls_base='#274a7d',ls_deep='#bb6237',ps1='#3b8255')
    names = dict(ls_base='LS baseline',ls_deep='LS deeper',ps1='PS1 DR2')
    fig,axes=plt.subplots(1,2,figsize=(9,3.8),sharey=True,layout='constrained')
    for ax,(cohort,rows) in zip(axes,data.items()):
        for i, (arm,label) in enumerate(names.items()):
            for d in (100,150):
                rr=[r for r in rows if float(r['D_kpc'])==d and r['survey']==arm]
                k=sum(r['spatial']=='True' for r in rr)
                if not rr:
                    continue
                p=k/len(rr)
                low,high=interval(k,len(rr))
                ax.errorbar(d+(i-1)*4,p,yerr=[[max(0,p-low)],[max(0,high-p)]],fmt='o',ms=4,capsize=2,
                            color=color[arm],label=label if d==100 else None)
        ax.set_title(cohort.replace('_',' ').title())
        ax.set_xlabel('Injected heliocentric distance (kpc)')
        ax.set_ylim(0,1)
    axes[0].set_ylabel('Spatial recovery fraction')
    axes[0].legend(frameon=False)
    save(fig,outputs/'matched_catalogue_response')
    if image:
        fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
        keys=sorted({r['cohort'] for r in image})
        for i,cohort in enumerate(keys):
            for j,arm in enumerate(('ls_base','ls_deep')):
                rr=[r for r in image if r['cohort']==cohort and r['arm']==arm]
                n=len(rr)
                if not n:
                    continue
                k=sum(r['spatial']=='True' for r in rr)
                p=k/n
                low,high=interval(k,n)
                ax.errorbar(i+(j-.5)*.18,p,yerr=[[max(0,p-low)],[max(0,high-p)]],fmt='o',capsize=3,
                            color=color[arm],label=names[arm] if i==0 else None)
        ax.set_xticks(range(len(keys)),[k.replace('_',' ') for k in keys])
        ax.set_ylim(0,1)
        ax.set_ylabel('Native-image spatial recovery fraction')
        ax.legend(frameon=False)
        save(fig,outputs/'native_image_response')


def run():
    out=Path('results/v14/efficiency')
    out.mkdir(exist_ok=True,parents=True)
    inputs, response, pairs = [], [], []
    data={}
    for cohort,region in (('south_ps1','south'),('north','north')):
        paths=sorted(Path(f'results/v13/selection_trials/{region}').glob('*.csv'))
        paths=[p for p in paths if not p.stem.endswith(('-response','-by-type'))]
        rows=[r for p in paths for r in read_csv(p)]
        data[cohort]=rows
        inputs.extend(paths)
        response.extend(binned(rows,cohort,'catalogue_shared_IMF_v13'))
        pairs.extend(paired_backgrounds(rows,cohort))
    sites={r['field']:r['cohort'] for r in read_csv(Path('configs/v14/image_fields.csv'))}
    native = []
    image = sorted(Path('results/v14/image_response').glob('*-blind.csv'))
    for p in image:
        inputs.append(p)
        rows=[dict(r,cohort=sites[r['site']]) for r in read_csv(p)]
        native.extend(rows)
    for c in sorted({r['cohort'] for r in native}):
        response.extend(binned([r for r in native if r['cohort']==c],c,'real_CCD_release_reprocessing_v14'))
    write_csv(out/'conditional_response_grid.csv',response)
    write_csv(out/'background_bootstrap_paired.csv',pairs)
    if native:
        write_csv(out/'native_blind_trials.csv',native)
    controls=[]
    input_north=Path('results/v12/matched/north/tan_table8_common_mask.csv')
    input_south=Path('results/v12/matched/south/tan_table8_common_mask.csv')
    ls_path=Path('results/v12/table8/tan_table8_ls.csv')
    ls_cov={(r['field'],r['depth']):r for r in read_csv(ls_path)}
    inputs.extend((input_north,input_south,ls_path))
    for path in (input_north,input_south):
        for r in read_csv(path):
            depth={'ls_base':'base','ls_deep':'deep'}.get(r['survey'])
            source=ls_cov.get((r['field'],depth),{})
            semantic = ('tan_not_selected_at_published_threshold' if r['tan_passed']=='false' else 'tan_selected')
            counts = {k:source[k] for k in source if 'forced' in k or 'fitbits' in k}
            controls.append(dict(r, tan_selection=semantic,**counts))
    write_csv(out/'tan_table8_comparison.csv', controls)

    literature=out/'published_ps1_dr1_reference.csv'
    if literature.is_file():
        inputs.append(literature)
        by_site={(r['field'],r['trial']):r for r in read_csv(literature)}
        observed=defaultdict(dict)
        for cohort, rows in data.items():
            for row in rows:
                observed[cohort,row['field'],row['trial']][row['survey']]=row['spatial']
        support=defaultdict(list)
        for (cohort,field,trial), counts in observed.items():
            ans=by_site.get((field,trial),{})
            if ans.get('eligible')=='True' and ans.get('reference_at_expected_proxy'):
                point = (cohort,ans['D_kpc'],ans['rh_pc'],ans['expected_MV_proxy'])
                support[point].append((float(ans['reference_at_expected_proxy']),counts))
        write_csv(out/'published_comparison_by_grid.csv',[
            dict(cohort=key[0],D_kpc=key[1],rh_pc=key[2],M_V_proxy=key[3],trials=len(entries),
                 published_dr1_mean_probability=np.mean([x[0] for x in entries]),
                 ls_base_spatial=sum(x[1]['ls_base']=='True' for x in entries)/len(entries),
                 ls_deep_spatial=sum(x[1]['ls_deep']=='True' for x in entries)/len(entries),
                 internal_ps1_dr2_spatial=sum(x[1]['ps1']=='True' for x in entries)/len(entries))
            for key,entries in sorted(support.items())])

    weak_archive=Path('results/v5/weak/holdout/weak_reference_association.csv')
    weak_deep=Path('results/v6/verification/depth_DELVE_7.csv')
    weak_shared=Path('results/v4/matched/matched_survey_recovery.csv')
    inputs.extend((weak_archive,weak_deep,weak_shared))
    targets={'DELVE_3','DELVE_4','DELVE_5','DELVE_7'}
    weak = [dict(r,design='blinded_review_with_published_member_check')
            for r in read_csv(weak_archive) if r['object'] in targets and r['preferred_C']=='True']
    weak.extend(dict(r,object=r['name'],design='common_mask_review_budget') for r in read_csv(weak_shared)
                if r['name'] in targets)
    weak.extend(dict(r,object=r.get('name') or r.get('field') or 'DELVE_7',design='matched_depth_test')
                for r in read_csv(weak_deep))
    write_csv(out/'delve_weak_controls.csv',weak)

    plot(out,data,native)
    write_json(out/'manifest.json',dict(inputs={str(p):sha(p) for p in inputs}, native_stamps_completed=len(image),
               definitions='Catalogue experiments condition on empirical surrogate detection/shape response. '
               'Native CCD experiments are reported separately by deployment background and threshold. '
               'Binomial intervals are conditional on the sampled sites; the paired table resamples sites. '
               'Published PS1 DR1 and PS1 DR2 matched review comparisons have distinct denominators.'))


if __name__ == '__main__':
    run()
