"""Audit prespecified Tan Table 8 targets after a full-field blind scan."""

import argparse
import json
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import select
from ls_satsearch.group_budget import groups
from ls_satsearch.hypotheses import truth_branch
from ls_satsearch.run import field_cache, read_csv, recovery, settings, sha, write_csv
from ls_satsearch.search import CMD, exact_onoff, load_isochrone


def cutoff(path, channel='A_base'):
    if not path.is_file():
        return None
    thresholds = json.loads(path.read_text())['thresholds']
    return next((p['cutoff'] for p in thresholds if p['policy']==channel and p['budget']==.3), None)


def compare(rows, target, dm, rh, threshold, cfg):
    if not rows:
        return dict(n_positional_modes=0, loose_correct_mode=False, strict_correct_mode=False,
                    shortlist_match=False if threshold is not None else None)
    coords = SkyCoord([r['ra_deg'] for r in rows],[r['dec_deg'] for r in rows],unit='deg')
    offsets = target.separation(coords).arcmin
    delta = np.array([r['dm']-dm for r in rows])
    loose = offsets <= max(cfg['match_min_arcmin'], cfg['match_rh_factor']*rh)
    strict = (offsets <= rh) & (np.array([r['rh_arcmin'] for r in rows]) <= max(.5,2*rh))
    pos = np.flatnonzero(loose)
    if not len(pos):
        return compare([],target,dm,rh,threshold,cfg)
    best = pos[np.argmax([rows[i]['score'] for i in pos])]
    nearby = [dict(rows[i], offset_arcmin=offsets[i]) for i in pos]
    passing = threshold is not None and rows[best]['score']>=threshold
    shortlist = groups([dict(r, channel='A_base', ranking=r['score']) for r in rows
                        if threshold is not None and r['score']>=threshold])
    is_group = any(target.separation(SkyCoord(p['ra_deg'],p['dec_deg'],unit='deg')).arcmin <=
                   max(cfg['match_min_arcmin'],cfg['match_rh_factor']*rh) for p,_ in shortlist)
    return dict(n_positional_modes=len(nearby), blind_score=rows[best]['score'], blind_dm=rows[best]['dm'],
                blind_delta_dm=delta[best], blind_correct_dm=abs(delta[best])<=.25,
                blind_radius_arcmin=rows[best]['rh_arcmin'], blind_offset_arcmin=offsets[best],
                blind_offset_per_rh=offsets[best]/rh, blind_strict_position=strict[best],
                blind_rank=rows[best].get('rank'), blind_raw_peak_id=rows[best].get('raw_peak_id'),
                loose_correct_mode=np.any(loose & (abs(delta)<=.75)),
                strict_correct_mode=np.any(strict & (abs(delta)<=.25)),
                threshold_crossed=passing if threshold is not None else None,
                shortlist_match=is_group if threshold is not None else None,
                cutoff_correct_mode=np.any(loose & (abs(delta)<=.25) &
                    (np.array([r['score'] for r in rows])>=threshold)) if threshold is not None else None)


def read_peaks(path, branch):
    return [dict({k:float(row[k]) for k in ('x','y','ra_deg','dec_deg','dm','rh_arcmin','score')},
                 rank=row.get('rank'),raw_peak_id=row.get('raw_peak_id'))
            for row in read_csv(path) if row['method']=='A' and row['branch']==branch]


def cmd_audit(field, area, sources, cfg, template, target, dm, rh):
    sample,_,valid,mags,chosen = select(sources,field,area,cfg)
    x,y = field.xy(target.ra.deg,target.dec.deg)
    radius = max(.5,min(rh,max(cfg['radii_arcmin'])))
    xm,ym = field.xy(sources['RA'],sources['DEC'])
    inside = np.hypot(xm-x,ym-y) <= 1.5*radius
    center = chosen & inside
    if not len(sample):
        return dict(center_catalog_psf=0, center_catalog_extended=int((valid & ~chosen & inside).sum()))
    on,off,area_on,area_off = exact_onoff(field,x,y,radius,cKDTree(sample[:,:2]),area,
                                         CMD(sample,template,cfg).weights(dm)[0])
    record = dict(diagnostic_rh_arcmin=radius, center_catalog_psf=int(center.sum()),
                  center_catalog_extended=int((valid & ~chosen & inside).sum()),
                  fixed_cmd_on=on, fixed_cmd_off=off, fixed_area_on_arcmin2=area_on,
                  fixed_area_off_arcmin2=area_off)
    for bit,key in ((13,'cluster'),(17,'resolved')):
        record[f'center_psf_{key}'] = int((center & ((sources['MASKBITS'] & (1<<bit))!=0)).sum())
    if 'FITBITS' in sources.dtype.names:
        record['center_psf_forced'] = int((center & ((sources['FITBITS'] & 1)!=0)).sum())
        record['center_psf_gaia_pointsource'] = int((center & ((sources['FITBITS'] & (1<<12))!=0)).sum())
    for band in 'GR':
        invvar=sources[f'PSFDEPTH_{band}'][center]
        trans=sources[f'MW_TRANSMISSION_{band}'][center]
        use=(invvar>0)&(trans>0)&np.isfinite(invvar+trans)
        if use.any():
            record[f'center_depth5_{band.lower()}_median'] = np.median(
                22.5-2.5*np.log10(5/np.sqrt(invvar[use]))+2.5*np.log10(trans[use]))
    return record


def audit(output):
    root,data,_ = settings()
    reference = {r['key']:r for r in read_csv(Path(
        'references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv'))}
    rows = []
    for case in read_csv(Path('configs/v12/table8/benchmarks.csv')):
        field_id,region = case['field'],case['region']
        truth = reference[case['key']]
        target = SkyCoord(float(truth['ra']),float(truth['dec']),unit='deg')
        distance,radius,dm = (float(truth[k]) for k in ('distance','rhalf_sph_physical','distance_modulus'))
        rh = np.degrees(np.arctan(radius/(1000*distance)))*60
        branch = truth_branch(distance)
        for depth in ('base','deep'):
            row=dict(case,name=truth['name'],distance_kpc=distance,rh_pc=radius,rh_arcmin=rh,
                     truth_dm=dm,m_v=truth['M_V'],truth_branch=branch,depth=depth)
            path = Path(f'table8_v12_{region}/results/summary/{field_id}-{depth}/manifest.json')
            if not path.is_file():
                rows.append(dict(row, status='manifests_pending'))
                continue
            m=json.loads(path.read_text())
            row.update(status=m['status'],job=m['slurm_job_id'],field_area_deg2=m['area_deg2'],
                       manifest_sha256=sha(path))
            if m['status'] not in ('complete','no_usable_gr'):
                rows.append(row)
                continue
            cfg=m['config']
            field,sources,area,_ = field_cache(root,data,m['field'],cfg,None)
            model = load_isochrone(data/'resources'/cfg['isochrone'])
            details = recovery([],dict(name=truth['name'],ra_deg=target.ra.deg,dec_deg=target.dec.deg,
                                   D_kpc=distance,theta_h_arcmin=rh),field,area,cfg,depth)[0]
            row.update({k:details[k] for k in ('covered','core_valid_fraction','off_valid_fraction','scale_below_grid')})
            row.update(cmd_audit(field,area,sources,cfg,model,target,dm,rh))
            if m['status']=='complete':
                if depth=='base' and region=='north':
                    policy=Path(f'results/v11/north/{branch}/calibration/sky_group_policy.json')
                elif depth=='base' and branch=='main':
                    policy=Path('configs/v7/production.json')
                elif region=='south' and depth=='deep' and branch=='main':
                    policy=Path('results/v3/development_groups/all_A/sky_group_policy.json')
                else:
                    policy=None
                threshold=cutoff(policy,'A_deep' if depth=='deep' else 'A_base') if policy else None
                raw=read_peaks(data/f'runs/v12/{field_id}-{depth}/all_template_peaks.csv',branch)
                dedup=read_peaks(path.parent/'deduplicated_peaks.csv',branch)
                row.update({f'raw_{k}':v for k,v in compare(raw,target,dm,rh,None,cfg).items()})
                row.update(compare(dedup,target,dm,rh,threshold,cfg))
                row.update(frozen_policy=str(policy) if threshold is not None else None,
                           frozen_threshold=threshold)
            rows.append(row)
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'tan_table8_ls.csv',rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    audit(p.parse_args().output)
