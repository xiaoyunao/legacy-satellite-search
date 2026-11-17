"""Evaluate the North/South common-mask LS and PS1 comparison at equal sky-group budgets."""

import argparse
import json
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np

from ls_satsearch.group_budget import evaluate
from ls_satsearch.hypotheses import truth_branch
from ls_satsearch.matched import SURVEYS
from ls_satsearch.ps1_tiles import design
from ls_satsearch.run import config_path, read_csv, settings, sha, write_csv
from ls_satsearch.search import CMD, exact_onoff, load_isochrone
from scipy.spatial import cKDTree
import yaml

from v12_table8 import aperture_coverage, compare, cutoff, read_peaks


def run(region, output):
    _,data,_=settings()
    matched=yaml.safe_load(config_path('matched.yaml').read_text())
    cases={r['field']:r for r in read_csv(Path('configs/v12/table8/benchmarks.csv'))}
    gold={r['key']:r for r in read_csv(Path(
        'references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv'))}
    source=Path(f'matched_v12_{region}/results/matched')
    stats, audits = [], []
    for survey in SURVEYS:
        summary=source/survey/'summary'
        out=output/survey/'groups'
        dev={p.parent.name.removesuffix('-base') for p in summary.glob('*/manifest.json')
             if (m:=json.loads(p.read_text()))['status']=='complete' and m['field']['role']=='pilot_dev'}
        expect={s['id'] for s in matched['fields'] if s['role']=='pilot_dev'}
        if not expect <= dev:
            raise ValueError(f'{region}/{survey} lacks frozen development fields: {sorted(expect-dev)}')
        for branch in ('main','far'):
            groups=out if branch=='main' else out/'far'
            evaluate(summary,groups,branch=branch,channels_only=('A_base',))
            stats.extend(dict(region=region,survey=survey,**r) for r in
                         read_csv(groups/'sky_group_comparison.csv'))
        for s in matched['fields']:
            if s['id'] not in cases:
                continue
            case=cases[s['id']]
            target=gold[case['key']]
            dm,dist,pc=map(float,(target['distance_modulus'],target['distance'],target['rhalf_sph_physical']))
            rh=np.degrees(np.arctan(pc/(1000*dist)))*60
            ra,dec=float(target['ra']),float(target['dec'])
            p=summary/f"{s['id']}-base"/'manifest.json'
            row=dict(case, survey=survey, name=target['name'],D_kpc=dist,rh_pc=pc,rh_arcmin=rh,
                     dm=dm,status='pending')
            no_joint=source/'coverage'/f"{s['id']}.json"
            if not p.exists():
                if no_joint.exists():
                    row['status']=json.loads(no_joint.read_text())['status']
                audits.append(row)
                continue
            m=json.loads(p.read_text())
            row.update(status=m['status'],area_deg2=m['area_deg2'],job=m['slurm_job_id'],
                       manifest_sha256=sha(p))
            if m['status']!='complete':
                audits.append(row)
                continue
            cfg=m['config']
            field,_=design(s,matched)
            run_path=data/'runs/v12/matched'/survey/s['id']
            area=np.load(run_path/'coverage.npy',allow_pickle=False)
            sample=np.load(run_path/'sample.npy',allow_pickle=False)
            radius=max(.5,min(rh,max(cfg['radii_arcmin'])))
            x,y=field.xy(ra,dec)
            row.update(aperture_coverage(field,area,x,y,radius,cfg),
                       scale_above_grid=rh>max(cfg['radii_arcmin']))
            full_scale=aperture_coverage(field,area,x,y,max(.5,rh),cfg)
            row.update({f'true_scale_{k}':v for k,v in full_scale.items()})
            branch=truth_branch(dist)
            if branch=='far' and dm<=cfg['main_dm_max']:
                branch='main'
            policy=(out if branch=='main' else out/'far')/'sky_group_policy.json'
            cut=cutoff(policy)
            pos=SkyCoord(ra,dec,unit='deg')
            rows=read_peaks(p.parent/'deduplicated_peaks.csv',branch)
            row.update(compare(rows,pos,dm,rh,cut,cfg),cutoff=cut,branch=branch)
            model_path = (data/'resources/isochrones/ps1/bressan2012/iso_a12.0_z0.00010.dat'
                          if survey=='ps1' else data/'resources'/cfg['isochrone'])
            model=load_isochrone(model_path,bands=tuple(m['bands']))
            on,off,area_on,area_off=exact_onoff(field,x,y,radius,cKDTree(sample[:,:2]),area,
                                                CMD(sample,model,cfg).weights(dm)[0])
            in_core=np.hypot(sample[:,0]-x,sample[:,1]-y)<=1.5*radius
            row.update(analysis_rh_arcmin=radius,photometric_point_sources=in_core.sum(),cmd_on=on,
                       cmd_off=off,area_on_arcmin2=area_on,area_off_arcmin2=area_off)
            if in_core.any():
                mags=sample[in_core,2:4]
                snr=2.5/np.log(10)/sample[in_core,4:6]
                g5,r5=np.median(mags+2.5*np.log10(snr/5),axis=0)
                row.update(core_selected_g5_noise_proxy=g5,core_selected_r5_noise_proxy=r5)
            if survey=='ps1':
                parent=m['cutflow']['area']
                selected=m['cutflow']['area_psf']
                row.update(field_quality_gri_sources=parent,field_morphology_pointlike=selected,
                           field_morphology_other=parent-selected)
            audits.append(row)
    write_csv(output/'common_mask_comparison.csv',stats)
    write_csv(output/'tan_table8_common_mask.csv',audits)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('region',choices=('north','south'))
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
