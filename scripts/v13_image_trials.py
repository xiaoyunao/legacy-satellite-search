"""Generate compact populations and measure the native CCD-to-A response."""
import argparse
import json
import os
from pathlib import Path

import fitsio
import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import Field, load_bricks, sample_pixels, select, sweeps
from ls_satsearch.group_budget import groups, matches
from ls_satsearch.matched import joint_coverage, reddening
from ls_satsearch.run import field_cache, read_csv, settings, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone, scan
if __package__:
    from .v12_selection_stats import interval
else:
    from v12_selection_stats import interval

VERSION = os.environ.get('LS_SAT_IMAGE_VERSION', 'v13')
CONFIG = Path('configs') / VERSION
OUTPUT = Path('results') / VERSION / 'image_response'


def photon_seed(seed, trial):
    return int(np.random.SeedSequence([seed,trial,143]).generate_state(1)[0])


def context(name):
    site = next(r for r in read_csv(CONFIG/'image_fields.csv') if r['field']==name)
    plan = yaml.safe_load((CONFIG/'image_trials.yaml').read_text())
    backgrounds = Path('configs/v13/matched')
    if site.get('cohort') in ('south_delve', 'south_des'):
        search = Path('configs/v12/cohorts') / site['cohort'] / 'search.yaml'
    else:
        search = backgrounds / site['region'] / 'search.yaml'
    cfg = yaml.safe_load(search.read_text())
    return site, plan, cfg


def local_coordinates(site):
    return Field(float(site['ra_deg']), float(site['dec_deg']), .075, 1/6, buffer=0)


def template_paths(data, cfg):
    resources = data/'resources'
    return (resources/cfg['isochrone'],
            resources/'isochrones/des/bressan2012/iso_a12.0_z0.00010.dat')


def produce(name):
    _, data, _ = settings()
    site, plan, cfg = context(name)
    field = local_coordinates(site)
    native, decam = template_paths(data,cfg)
    model = load_isochrone(native)
    dec = load_isochrone(decam)
    ps1_path = data/'resources'/plan['ps1_template'] if plan.get('ps1_template') else None
    ps1_values = None
    if ps1_path is not None:
        ps1_model = load_isochrone(ps1_path,bands=('gP1','rP1'))
        def physical_rows(path):
            with path.open() as handle:
                header=next(line[1:].split() for line in handle if line.startswith('#') and 'M_ini' in line and 'int_IMF' in line)
            phase='stage' if 'stage' in header else 'label'
            return np.loadtxt(path,usecols=[header.index(k) for k in ('M_ini','int_IMF',phase)]),header
        identity,_=physical_rows(native)
        other_identity,ps1_header=physical_rows(ps1_path)
        if not np.array_equal(identity,other_identity):
            raise ValueError('PS1 and native image populations do not share physical rows')
        ps1_values=np.column_stack([ps1_model[0],np.loadtxt(ps1_path,usecols=ps1_header.index('iP1'))])
    with native.open() as f:
        columns = next(line[1:].split() for line in f if line.startswith('#') and 'int_IMF' in line)
    iz = ('i','z') if site['region']=='south' else ('iP1','zP1')
    other = np.loadtxt(native,usecols=[columns.index(b) for b in iz])
    if site['region']=='north':
        gi = model[0][:,0]-other[:,0]
        other[:,1] += .03664-.11084*gi+.04477*gi**2-.01223*gi**3
    magnitudes = np.column_stack([model[0], other])
    proxy = 10**(-.4*(dec[0][:,0]-.59*(dec[0][:,0]-dec[0][:,1])-.01))
    valid = np.any(np.column_stack([model[0],dec[0]]) < np.array([26,25.5]*2) - 20, axis=1)
    storage = data/f'image-{VERSION}'/name
    for number, (distance, rh, mv) in enumerate(plan['conditions']):
        stage = storage/f'trial{number:02d}'
        stage.mkdir(exist_ok=True,parents=True)
        rng = np.random.default_rng([plan['seed'],number])
        dm = 5*np.log10(distance)+10
        arc = np.rad2deg(np.arctan(rh/(1000*distance)))*60
        # Displace the artificial system within the stamp independently of the real objects.
        center = rng.uniform(-.40,.40,size=2)
        total = 10**(-.4*mv)/(dec[1]@proxy)
        draw = rng.poisson(total*model[1])
        indices = np.repeat(np.arange(len(draw)), draw*valid)
        q = rng.random(len(indices))
        angle = rng.uniform(0,2*np.pi,len(indices))
        xy = center + (arc*np.sqrt(q/(1-q)))[:,None]*np.column_stack([np.cos(angle),np.sin(angle)])
        retain = np.linalg.norm(xy,axis=1) < plan['splice_radius_arcmin']-.03
        xy, indices = xy[retain], indices[retain]
        ra, dec_ = field.sky(*xy.T)
        ebv = reddening(ra,dec_)
        extinction = [3.214,2.165,1.592,1.211] if site['region']=='south' else [3.258,2.176,1.592,1.199]
        observed = magnitudes[indices]+dm+ebv[:,None]*np.array(extinction)
        extra_bands=('ps1_g0','ps1_r0','ps1_i0') if ps1_values is not None else ()
        bands = np.empty(len(indices),dtype=[(k,'f8') for k in
                         ('ra','dec','g0','r0','flux_g','flux_r','flux_i','flux_z')+extra_bands])
        bands['ra'],bands['dec'] = ra,dec_
        bands['g0'],bands['r0'] = (magnitudes[indices,:2]+dm).T
        for idx, band in enumerate('griz'):
            bands[f'flux_{band}'] = 10**(-.4*(observed[:,idx]-22.5))
        if ps1_values is not None:
            for idx,band in enumerate(extra_bands): bands[band]=ps1_values[indices,idx]+dm
        np.save(stage/'truth.npy',bands,allow_pickle=False)
        ra0,dec0 = field.sky(*center)
        extra_meta=dict(ps1_model_sha256=sha(ps1_path),shared_population_rows_verified=True,
                        source_poisson_seed=photon_seed(plan['seed'],number)) if ps1_path else {}
        write_json(stage/'truth.json',dict(D_kpc=distance,rh_pc=rh,expected_MV_proxy=mv,
                   realized_MV_proxy=-2.5*np.log10(draw@proxy) if draw.any() else None,
                   N_imf=int(draw.sum()),N_rendered=len(indices),trial=number,
                   theta_h_arcmin=arc,truth_ra_deg=ra0,truth_dec_deg=dec0,
                   ra_deg=ra0,dec_deg=dec0,seed=[plan['seed'],number],model_sha256=sha(native),**extra_meta))


def native_table(folder):
    cat, = sorted(folder.glob('tractor/*/tractor-*.fits'))
    rows = fitsio.read(cat,upper=True)
    return rows, cat


def match_to(src, candidates, radius, field):
    if len(src)==0:
        return np.empty(0,dtype=int)
    if len(candidates) == 0:
        return np.full(len(src), -1, dtype=int)
    tree = cKDTree(np.column_stack(field.xy(*candidates.T)))
    xy = np.column_stack(field.xy(*src.T))
    neighbors = tree.query_ball_point(xy,radius/60)
    order = sorted((float(sum((xy[i]-tree.data[j])**2)),i,j)
                   for i,js in enumerate(neighbors) for j in js)
    used=set()
    match = np.full(len(xy),-1,dtype=int)
    for _,i,j in order:
        if match[i]<0 and j not in used:
            match[i]=j
            used.add(j)
    return match


def replaced(field, site, exterior, inner, limit):
    center = field.xy(float(site['ra_deg']),float(site['dec_deg']))
    return np.vstack([exterior[np.linalg.norm(exterior[:,:2]-center,axis=1)>=limit],
                      inner[np.linalg.norm(inner[:,:2]-center,axis=1)<limit]])


def blind(sample, field, mask, model, cfg, truth, cut, *, followup=False):
    _, peaks, _, cmd = scan(sample,field,mask,model,cfg)
    rows = [dict(r,channel='A_base',ranking=r['score']) for r in peaks if r['branch']=='main']
    hypotheses = groups(rows)
    record = matches(hypotheses, truth, cut, cfg)
    if followup:
        from ls_satsearch.review import fit_at_peak
        from ls_satsearch.search import point_fit

        record.update(c_modes_fit=0, passes_C_stability_proxy=False)
        if record['spatial']:
            # Identify the injected system only after A's sky groups have been
            # constructed. Supply C with every passing mode in its A group.
            linked = next((modes for anchor, modes in hypotheses
                           if matches([(anchor,modes)], truth, cut, cfg)['spatial']), [])
            fitted = [fit for peak in linked if peak['ranking'] >= cut
                      if (fit := fit_at_peak(peak, sample, field, mask, cmd)) is not None]
            if fitted:
                peak, fit, members, probability, ratio = max(fitted, key=lambda v: v[1]['ts'])
                remove = members[np.argsort(probability)[-3:]]
                take = np.delete(np.arange(len(sample)), remove)
                from ls_satsearch.search import CMD
                reduced = sample[take]
                masked_cmd = CMD(reduced, model, cfg)
                stable, _, _ = point_fit(reduced, masked_cmd, field, mask, peak)
                remaining_ts = stable['ts'] if stable is not None else 0.
                record.update(c_modes_fit=len(fitted), c_ts=fit['ts'], c_after_top3=remaining_ts,
                              c_dm=peak['dm'], c_rh_arcmin=peak['rh_arcmin'],
                              passes_C_stability_proxy=bool(remaining_ts >= 1.))
    return record


def photometry(native, match, field, area, cfg):
    chosen = select(native,field,area,cfg)[4]
    take=np.maximum(match,0)
    valid=match>=0
    psf = valid & (np.char.strip(native['TYPE'].astype(str))[take]=='PSF')
    kept=valid & chosen[take]
    return psf,kept


def counts(denom,det,point,selected):
    num = tuple(int(v.sum()) for v in (denom,denom&det,denom&point,denom&selected))
    result=dict(zip(('exposed','detected','psf','selected'),num))
    for label,k,n in zip(('p_detected','p_psf_given_detected','p_selected_given_psf'),num[1:],num):
        lo,hi=interval(k,n) if n else (None,None)
        result.update({label:k/n if n else None,label+'_lo':lo,label+'_hi':hi})
    return result


def measure(name, allow_partial=False):
    root,data,_ = settings()
    site,plan,cfg=context(name)
    storage=data/f'image-{VERSION}'/name
    requested = sorted(storage.glob('trial*'))
    ready = [p for p in requested if any(p.glob('tractor/*/tractor-*.fits'))
             and (p/'injected_exposures.npy').is_file() and (p/'initial_detection.npy').is_file()]
    if not ready or (not allow_partial and len(ready) != len(plan['conditions'])):
        raise ValueError(f'{name}: {len(ready)} of {len(plan["conditions"])} CCD trials have final products')
    blank,blank_cat=native_table(storage/'blank')
    field=local_coordinates(site)
    radius=plan['matching_radius_arcsec']
    splice=plan['splice_radius_arcmin']
    blank_sky=np.column_stack([blank['RA'],blank['DEC']])
    blank_initial=np.load(storage/'blank'/'initial_detection.npy',allow_pickle=False)
    release,_=sweeps(root,field,site['region'])
    real_sky=np.column_stack([release['RA'],release['DEC']])
    sep=np.hypot(*field.xy(*real_sky.T))
    matched=match_to(real_sky[sep<splice],blank_sky,radius,field)
    region=site['region']
    background=site['background']
    cohort = site.get('cohort', '')
    deep_south = cohort in ('south_delve', 'south_des')
    census_mask = data/'resources/ps1/ps1d_mask_v2.1.fits'
    if deep_south:
        config_path = Path('configs/v12/cohorts') / cohort / 'fields.yaml'
        spec = next(r for r in yaml.safe_load(config_path.read_text())['fields'] if r['id'] == background)
    else:
        config_path=Path('configs/v13/matched')/region/'matched.yaml'
        matched_plan=yaml.safe_load(config_path.read_text())
        spec=next(r for r in matched_plan['fields'] if r['id']==background)
        spec=dict(spec,width=matched_plan['width_deg'],buffer_arcmin=matched_plan['buffer_arcmin'])
        cfg.update(dm=matched_plan['dm'],radii_arcmin=matched_plan['radii_arcmin'],methods=['A'],
                   review_budgets_deg2=matched_plan['review_budgets_deg2'])
    search_field,released,ls_area,release_inputs=field_cache(root,data,spec,cfg,load_bricks(root,region))
    area = ls_area if deep_south else joint_coverage(search_field,ls_area,census_mask)
    model=load_isochrone(template_paths(data,cfg)[0])
    native_blank_header=fitsio.read_header(blank_cat)
    parents=cKDTree(np.column_stack(field.xy(*blank_sky.T)))
    rows, outcomes, input_refs = [], [], []
    for arm in (('ls_base',) if deep_south else ('ls_base','ls_deep')):
        actual = cfg.copy()
        if arm == 'ls_deep':
            for band in 'gr':
                actual[f'{band}_max'] += .5
        if deep_south:
            policy = Path(f'results/v11/{cohort}/main/calibration/sky_group_policy.json')
        else:
            policy = Path(f'results/v12/matched/{region}/{arm}/groups/sky_group_policy.json')
        policy_data=json.loads(policy.read_text())
        for group in (policy_data['recipe'],policy_data['limits']['base']):
            if any(actual.get(k)!=v for k,v in group.items()):
                raise ValueError(f'{arm}: image trial differs from frozen matched recipe')
        cut=next(r['cutoff'] for r in policy_data['thresholds'] if r['budget']==.3)
        exterior=select(released,search_field,area,actual)[0]
        clean=select(blank,search_field,area,actual)[0]
        background_sample=replaced(search_field,site,exterior,clean,splice)
        c=dict(actual,dm=[16.5,actual.get('main_dm_max', 20.75),actual['dm'][2]])
        for stage in ready:
            truth=json.loads((stage/'truth.json').read_text())
            trial=str(truth['trial'])
            sample,cat=native_table(stage)
            t=np.load(stage/'truth.npy',allow_pickle=False)
            inject_sky=np.column_stack([t['ra'],t['dec']])
            pixels=np.column_stack(field.xy(*inject_sky.T))
            nobs=np.load(stage/'injected_exposures.npy',allow_pickle=False)
            observed=(nobs[:,:2]>0).all(axis=1)
            observed &= area[sample_pixels(search_field,area,*search_field.xy(*inject_sky.T))]
            detection=np.load(stage/'initial_detection.npy',allow_pickle=False)
            new_first=match_to(detection,blank_initial,radius,field)<0
            found_first=match_to(inject_sky,detection[new_first],radius,field)>=0
            final_sky=np.column_stack([sample['RA'],sample['DEC']])
            novel=match_to(final_sky,blank_sky,radius,field)<0
            finals=match_to(inject_sky,final_sky[novel],radius,field)
            final_match=np.where(finals>=0,np.flatnonzero(novel)[np.maximum(finals,0)],-1) if novel.any() else finals
            det=final_match>=0
            psf, selected=photometry(sample,final_match,search_field,area,actual)
            # Real faint blending is counted as a failure when the existing blank source remains.
            clearance=parents.query(pixels)[0]*60
            for low,high in ((-10,30),(20,22),(22,23),(23,23.5),(23.5,24),(24,25),(25,26)):
                valid=observed & (t['g0']>=low) & (t['g0']<high)
                for context_,env in (('all',np.ones(len(t),dtype=bool)),('near_2arcsec',clearance<2),
                                     ('clear_2arcsec',clearance>=2)):
                    use=valid&env
                    rows.append(dict(site=name,trial=trial,arm=arm,g_lo=low,g_hi=high,environment=context_,
                                     detected_initial=int((use&found_first).sum()),**counts(use,det,psf,selected)))
            after=replaced(search_field,site,exterior,select(sample,search_field,area,actual)[0],splice)
            blank_fit=blind(background_sample,search_field,area,model,c,truth,cut)
            injection=blind(after,search_field,area,model,c,truth,cut,followup=VERSION!='v13')
            outcomes.append(dict(site=name,arm=arm,cutoff=cut,blank_spatial=blank_fit['spatial'],
                                 N_exposed=int(observed.sum()),N_final=int((observed&det).sum()),
                                 N_psf=int((observed&psf).sum()),N_used=int((observed&selected).sum()),
                                 **truth,**injection))
            input_refs.append(dict(trial=trial,arm=arm,tractor_sha256=sha(cat),
                                   policy_sha256=sha(policy)))
    OUTPUT.mkdir(exist_ok=True,parents=True)
    write_csv(OUTPUT/f'{name}-stages.csv',rows)
    write_csv(OUTPUT/f'{name}-blind.csv',outcomes)
    write_json(OUTPUT/f'{name}.json',dict(job=os.getenv('SLURM_JOB_ID'),native_version=native_blank_header.get('LEGPIPEV'),
               blank_sha256=sha(blank_cat),plan_sha256=sha(CONFIG/'image_trials.yaml'),
               blank_inside_published=int((sep<splice).sum()),blank_matches_published=int((matched>=0).sum()),
               outer_catalog_inputs=release_inputs,matched_config_sha256=sha(config_path),
               ps1_defined_mask_sha256=None if deep_south else sha(census_mask),
               inputs=input_refs,requested_trials=len(plan['conditions']),measured_trials=len(ready),
               scope='Rerun on real calibrated CCDs; released mask and preserved outer background. '
               'Unique 0.8 arcsec matching, counting existing sources present in the blank as blends. '
               'Image experiments assess conditional response in selected stamps.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare','measure'))
    p.add_argument('site')
    p.add_argument('--allow-partial',action='store_true')
    a=p.parse_args()
    if a.mode=='prepare':
        produce(a.site)
    else:
        measure(a.site,allow_partial=a.allow_partial)
