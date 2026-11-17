"""Independent PS1 photometric test of a position frozen by the LS scan."""

import csv
import argparse
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from astropy.coordinates import SkyCoord
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import binom
import yaml

from .data import Field, sample_pixels
from .group_budget import groups
from .matched import PS1_MODEL, joint_coverage, reddening
from .ps1_probe import URL
from .ps1_tiles import COLUMNS, download
from .review import fit_at_peak
from .run import config_path, field_cache, sha, settings, write_csv, write_json
from .search import CMD, exact_onoff, load_isochrone, point_fit, scan

OUT = Path('results/verification')


def setup(policy=None):
    root, data, cfg = settings()
    plan = yaml.safe_load((policy or config_path('followup.yaml')).read_text())
    prior = Path(os.environ['LS_SAT_V5'])
    m = Path(plan['field_manifest']) if 'field_manifest' in plan else (
        prior/'batches/batch1/results/summary'/f"{plan['field']}-base/manifest.json")
    spec = json.loads(m.read_text())['field']
    field, sources, area, _ = field_cache(root,data,spec,cfg,None)
    return plan, cfg, data, field, sources, area


def ps1_sample(plan, field, area, cache):
    query = URL+'.csv?'+urlencode(dict(ra=field.ra,dec=field.dec,radius=plan['ps1_radius_deg'],
                                   primaryDetection=1,columns='['+','.join(COLUMNS)+']',
                                   pagesize=25000,sort_by='objID.asc'))
    path = cache/'ps1.csv'
    payload = path.read_bytes() if path.exists() else download(query)
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if not reader.fieldnames or not set(COLUMNS)<=set(reader.fieldnames):
        raise ValueError('Invalid PS1 response')
    rows = {r['objID']: r for r in reader}
    if len(rows)>=25000 or not rows:
        raise ValueError('Expected a nonempty single-page PS1 cone')
    path.write_bytes(payload)
    columns = [c for c in COLUMNS if c not in ('objID','primaryDetection')]
    values = np.array([[float(r[k] or 'nan') for k in columns] for r in rows.values()])
    ra,dec,g,r,ge,re,i,k,ie = values.T
    errmax = 2.5/np.log(10)/plan['ps1_min_snr']
    good = (np.isfinite(values).all(1)&(np.min(values[:,2:],axis=1)>0)&
            (np.maximum.reduce([ge,re,ie])<=errmax)&(i-k<plan['ps1_ikron_delta']))
    x,y=field.xy(ra,dec)
    good &= (abs(x)<field.limit)&(abs(y)<field.limit)&area[sample_pixels(field,area,x,y)]
    ebv = reddening(ra[good],dec[good])
    g0,r0 = g[good]-3.172*ebv,r[good]-2.271*ebv
    sample = np.column_stack([x[good],y[good],g0,r0,ge[good],re[good]])
    selected = np.isfinite(sample).all(1)&(sample[:,2:4]<=plan['ps1_magnitude_caps']).all(1)
    return sample[selected],dict(query=query,sha256=sha(path),unique_primary=len(rows),selected=int(selected.sum()))


def observing_proxy(field, source, centers):
    mag = np.log10(np.maximum(source['PSFDEPTH_G'],1.e-10))*1.25
    seeing = source['PSFSIZE_G']
    ebv = source['EBV']
    good=(source['PSFDEPTH_G']>0)&(seeing>0)&np.isfinite(mag+seeing+ebv)
    xy=np.column_stack(field.xy(source['RA'][good],source['DEC'][good]))
    idx=cKDTree(xy).query(centers,k=32)[1]
    return np.column_stack([np.median(v[good][idx],axis=1) for v in (mag,seeing,ebv)])


def without_foreground(sample, field, cache):
    from .candidate_archives import GAIA, GAIA_MIRROR, tap

    columns=('ra','dec','parallax','parallax_error','ruwe')
    query=(f"SELECT TOP 12000 {','.join(columns)} FROM gaiadr3.gaia_source "
           f"WHERE 1=CONTAINS(POINT(ra,dec),CIRCLE({field.ra},{field.dec},0.29))")
    path=cache/'gaia-wide.csv'
    try:
        rows=tap(GAIA,query,columns,path,'GET')
    except (OSError,ValueError):
        rows=tap(GAIA_MIRROR,query,columns,path,'GET')
    if not rows or len(rows)>=12000:
        raise ValueError('Unexpected Gaia control-cone size')
    foreground=[r for r in rows if r['ruwe'] and float(r['ruwe'])<1.4 and
                r['parallax_error'] and float(r['parallax_error'])>0 and
                float(r['parallax'])>max(.15,3*float(r['parallax_error']))]
    match=np.zeros(len(sample),dtype=bool)
    if foreground:
        ps=SkyCoord(*field.sky(*sample[:,:2].T),unit='deg')
        sky=SkyCoord([float(r['ra']) for r in foreground],
                     [float(r['dec']) for r in foreground],unit='deg')
        match=ps.match_to_catalog_sky(sky)[1].arcsec<=.8
    return sample[~match],dict(gaia_rows=len(rows),gaia_sha256=sha(path),removed=int(match.sum()))


def review_local_peaks(sample, cmd, field, area, peaks, prefix):
    """Compare the strongest local A groups under a common PS1 C refit."""
    proposals = groups([dict(peak, channel='A_base', ranking=peak['score']) for peak in peaks])
    shortlist = proposals[:12]
    if not shortlist:
        raise ValueError('The PS1 scan yielded no hypotheses for C review')
    score_floor = shortlist[-1][0]['score']
    rows = []
    for rank, (anchor, modes) in enumerate(shortlist, start=1):
        base = dict(group_A_rank=rank, A_score=anchor['score'],
                    A_offset_arcmin=float(np.hypot(anchor['x'], anchor['y'])))
        for mode_index, mode in enumerate(modes, start=1):
            if mode['score'] < score_floor:
                continue
            out = fit_at_peak(mode, sample, field, area, cmd)
            summary = dict(base, mode_index=mode_index, mode_A_score=mode['score'],
                           seed_dm=mode['dm'], seed_rh_arcmin=mode['rh_arcmin'])
            if out is not None:
                trial, fit, *_ = out
                summary.update(C_TS=fit['ts'], fit_dm=trial['dm'], fit_rh_arcmin=trial['rh_arcmin'],
                               fit_offset_arcmin=float(np.hypot(trial['x'], trial['y'])))
            rows.append(summary)
    write_csv(OUT/f'{prefix}_local_A_to_C.csv', rows)
    write_json(OUT/f'{prefix}_local_A_to_C.json', dict(job=os.environ.get('SLURM_JOB_ID'),
               group_total=len(proposals), groups_refit=len(shortlist), score_floor=score_floor,
               modes_attempted=len(rows), modes_fit=sum('C_TS' in row for row in rows)))


def run(gaia_veto=False, local_review=False, policy=None):
    policy = policy or config_path('followup.yaml')
    plan,cfg,data,old,sources,old_area = setup(policy)
    radii=plan['ps1_scan_radii']
    cfg.update(radii_arcmin=radii,dm=plan['ps1_scan_dm'],methods=['A'],coverage_subdivision=2,
               g_max=plan['ps1_magnitude_caps'][0], r_max=plan['ps1_magnitude_caps'][1])
    field=Field(plan['ra_deg'],plan['dec_deg'],plan['ps1_scan_width_deg'],min(radii)/3,
                buffer=plan['ps1_scan_buffer_arcmin'])
    n=field.n*cfg['coverage_subdivision']
    axis=(np.arange(n)+.5)*2*field.limit/n-field.limit
    ra,dec=field.sky(*np.meshgrid(axis,axis))
    x,y=old.xy(ra,dec)
    area=old_area[sample_pixels(old,old_area,x,y)]
    area &= np.hypot(*np.meshgrid(axis,axis))<60*plan['ps1_radius_deg']
    area=joint_coverage(field,area,data/'resources/ps1/ps1d_mask_v2.1.fits')
    cache=data/'resources'/plan.get('scratch_revision','v6')/plan['candidate']
    cache.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    sample,inputs=ps1_sample(plan,field,area,cache)
    parent_tree=cKDTree(sample[:,:2])
    prefix='ps1_gaia_veto' if gaia_veto else 'ps1'
    prefix=plan.get('output_prefix','')+prefix
    if gaia_veto:
        sample,veto=without_foreground(sample,field,cache)
        inputs.update(veto)
    model=load_isochrone(data/'resources'/PS1_MODEL,bands=('gP1','rP1'))
    cmd=CMD(sample,model,cfg)
    locus,ratio=cmd.weights(plan['dm'])
    tree=cKDTree(sample[:,:2])
    rh=plan['rh_arcmin']

    # Match the control geometry on enclosing PS1 and LS photometric conditions.
    rng=np.random.default_rng(plan['seed'])
    n=plan['control_draws']
    lo,hi=plan['control_radius_arcmin']
    rr=np.sqrt(rng.uniform(lo*lo,hi*hi,n))
    th=rng.uniform(0,2*np.pi,n)
    xy=np.vstack([[0.,0.], np.column_stack([rr*np.cos(th),rr*np.sin(th)])])
    old_x,old_y=old.xy(*field.sky(*xy.T))
    conditions=observing_proxy(old,sources,np.column_stack([old_x,old_y]))
    density=parent_tree.query_ball_point(xy,3.,return_length=True)-parent_tree.query_ball_point(xy,2.,return_length=True)
    feature=np.column_stack([conditions,density])
    normal=np.maximum(np.std(feature[1:],axis=0),[.02,.02,.002,1.])
    dist=np.linalg.norm((feature-feature[0])/normal,axis=1)
    order=np.argsort(dist[1:])+1
    rows=[]
    for j in np.r_[0,order]:
        x,y=xy[j]
        on,off,a_on,a_off=exact_onoff(field,x,y,rh,tree,area,locus)
        if a_on<=0 or a_off<=0 or a_on<.8*np.pi*(1.5*rh)**2:
            if j==0:
                raise ValueError('Insufficient coverage at frozen position')
            continue
        peak=dict(x=x,y=y,dm=plan['dm'],rh_arcmin=rh)
        fit,_,_=point_fit(sample,cmd,field,area,peak,ratio=ratio)
        rows.append(dict(target=j==0,ps1_cmd_n_on=int(on),ps1_cmd_n_off=int(off),
                         on_area_arcmin2=a_on,off_area_arcmin2=a_off,
                         onoff_tail=float(binom.sf(on-1,on+off,a_on/(a_on+a_off))),
                         C_TS=float(fit['ts']) if fit else None,match_distance=float(dist[j]),
                         local_depth_proxy=float(conditions[j,0]),seeing=float(conditions[j,1]),
                         ebv=float(conditions[j,2]),ps1_annulus_count=int(density[j])))
        if len(rows)==1+plan['control_neighbors']:
            break
    if not local_review:
        write_csv(OUT/f'{prefix}_fixed_and_controls.csv',rows)
    target=rows[0]
    control=[r for r in rows[1:] if r['C_TS'] is not None]
    result=dict(target,inputs=inputs,config_sha256=sha(policy),
                job=os.environ.get('SLURM_JOB_ID'),control_n=len(rows)-1,
                at_least_as_small_tail=sum(r['onoff_tail']<=target['onoff_tail'] for r in rows[1:]),
                control_C_n=len(control))
    if target['C_TS'] is not None:
        result['C_TS_at_least_as_high']=sum(r['C_TS']>=target['C_TS'] for r in control)
    _,peaks,wall,_=scan(sample,field,area,model,cfg)
    if local_review:
        review_local_peaks(sample, cmd, field, area, peaks, prefix)
        return
    nearby=[r for r in peaks if np.hypot(r['x'],r['y'])<=1.5]
    write_csv(OUT/f'{prefix}_blind_nearby_peaks.csv',nearby,keys=('method','x','y','dm','score'))
    result.update(blind_peaks_within_1p5arcmin=len(nearby), ps1_scan_seconds=wall,
                  blind_total_peaks=len(peaks))
    if peaks:
        best=max(peaks,key=lambda p:p['score'])
        result['strongest_blind_peak']=dict(score=best['score'],dm=best['dm'],rh_arcmin=best['rh_arcmin'],
                                           offset_arcmin=float(np.hypot(best['x'],best['y'])))
    write_json(OUT/f'{prefix}_summary.json',result)
    radial=np.hypot(*sample[:,:2].T)
    fig,axes=plt.subplots(1,2,figsize=(7,3.8),sharey=True,layout='constrained')
    center=radial<=plan['center_aperture_arcmin']
    for ax,sel,title in zip(axes,[center,(radial>3.5*rh)&(radial<=6*rh)],['Fixed centre','Local annulus']):
        ax.scatter(sample[sel,2]-sample[sel,3],sample[sel,2],s=15)
        gr=model[0]
        ax.scatter(gr[:,0]-gr[:,1],gr[:,0]+plan['dm'],s=1,color='tab:red')
        ax.set(xlim=(-.5,1.7),ylim=(24.3,16),xlabel='PS1 (g − r)₀',title=title)
    axes[0].set_ylabel('PS1 g₀')
    fig.savefig(OUT/f'{prefix}_independent_cmd.png',dpi=155)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gaia-veto',action='store_true')
    parser.add_argument('--review-local', action='store_true')
    parser.add_argument('--plan',type=Path)
    args = parser.parse_args()
    run(args.gaia_veto, args.review_local, args.plan)
