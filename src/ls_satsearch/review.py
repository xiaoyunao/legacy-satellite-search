"""Review retained L0 peaks with local image and catalog diagnostics on NERSC."""

import argparse
import csv
import json
from pathlib import Path

import fitsio
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from .data import load_bricks, select
from .plots import candidate
from .run import field_cache, quantile, read_csv, runs_path, settings, write_csv
from .search import CMD, exact_onoff, load_isochrone, point_fit


def convert_peak(p):
    p = dict(p)
    for k in ('x', 'y', 'dm', 'rh_arcmin', 'ra_deg', 'dec_deg', 'score'):
        p[k] = float(p[k])
    return p


def fit_at_peak(peak, sample, field, area, cmd):
    best = None
    for d in (-.25, 0, .25):
        trial = dict(peak, dm=peak['dm'] + d)
        _, ratio = cmd.weights(trial['dm'])
        for r in (.7, 1., 1.4):
            trial['rh_arcmin'] = r * peak['rh_arcmin']
            fit, idx, prob = point_fit(sample, cmd, field, area, trial, ratio=ratio)
            if fit is not None and (best is None or fit['ts'] > best[1]['ts']):
                best = dict(trial), fit, idx, prob, ratio
    if best is None:
        return None
    anchor, _, _, _, ratio = best
    step = max(field.step, min(2., anchor['rh_arcmin']/2))
    out = best
    for dx, dy in ((step,0),(-step,0),(0,step),(0,-step)):
        trial = dict(anchor, x=anchor['x']+dx, y=anchor['y']+dy)
        fit, idx, prob = point_fit(sample, cmd, field, area, trial, ratio=ratio)
        if fit is not None and fit['ts'] > out[1]['ts']:
            out = (trial, fit, idx, prob, ratio)
    trial = out[0]
    trial['ra_deg'], trial['dec_deg'] = field.sky(trial['x'],trial['y'])
    return out


def observing_page(path, root, bricks, data, valid, field, peak, row):
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), layout='constrained')
    x, y = field.xy(data['RA'], data['DEC'])
    rh = peak['rh_arcmin']
    lim = min(6*rh, field.limit - max(abs(peak['x']), abs(peak['y'])))
    xx, yy = x - peak['x'], y - peak['y']
    use = valid & (abs(xx) <= lim) & (abs(yy) <= lim)
    depth = data['PSFDEPTH_G'][use]
    t = data['MW_TRANSMISSION_G'][use]
    with np.errstate(divide='ignore', invalid='ignore'):
        values = [22.5 - 2.5*np.log10(5/np.sqrt(depth)) + 2.5*np.log10(t),
                  data['PSFSIZE_G'][use],
                  data['EBV'][use] if 'EBV' in data.dtype.names else np.full(use.sum(), np.nan)]
    for ax, val, title in zip(axes.flat, values, ('g₀ 5σ PSF depth (mag)', 'g PSF size (arcsec)', 'E(B−V) (mag)')):
        quant = quantile(val)
        if quant is not None:
            lo, mid, hi = quant
            m = ax.scatter(xx[use], yy[use], c=val, s=8, vmin=lo, vmax=max(hi, lo+1e-4), cmap='viridis')
            fig.colorbar(m, ax=ax, shrink=.8, label=f'Local median {mid:.3f}')
        else:
            ax.text(.5, .5, 'Unavailable', transform=ax.transAxes, ha='center')
        ax.add_patch(plt.Circle((0, 0), rh, fill=False, color='tab:red'))
        ax.set(xlim=(-lim,lim), ylim=(-lim,lim), title=title, xlabel='East (arcmin)', ylabel='North (arcmin)')
        ax.set_aspect('equal')
    axes[1,1].axis('off')
    axes[1,1].text(.5,.5,'Local g and r cutouts in the companion panel',ha='center',va='center')
    nearest = row.get('nearest_known', '')
    sep = row.get('nearest_known_arcmin', '')
    fig.suptitle(f"L0 · {row['field_id']} · {peak['method']} rank {peak['rank']}\n"
                 f"Nearest cataloged object: {nearest} ({float(sep):.1f}′)" if sep else "L0 peak")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {f'{k}_local_p10_p50_p90': quantile(v) for k, v in zip(('g_depth', 'g_seeing', 'ebv'), values)}


def image_cutouts(path, root, bricks, field, peak, member_xy, prob):
    ra,dec=peak['ra_deg'],peak['dec_deg']
    inside=((ra-bricks['RA1'])%360 < (bricks['RA2']-bricks['RA1'])%360
            ) & (bricks['DEC1'] <= dec) & (dec < bricks['DEC2'])
    if not np.any(inside):
        return False
    name=bricks['BRICKNAME'][inside][0].strip()
    base=root/'south/coadd'/name[:3]/name/f'legacysurvey-{name}'
    files=[Path(f'{base}-image-{band}.fits.fz') for band in 'gr']
    if not all(p.is_file() for p in files):
        return False
    fig,axes=plt.subplots(2,4,figsize=(12,6),layout='constrained')
    coords=field.sky(*member_xy.T)
    strong=np.argsort(prob)[::-1][:3]
    for band,file,row in zip('gr',files,axes):
        with fitsio.FITS(file) as f:
            hdu=f[1]
            hdr=dict(hdu.read_header())
            allowed=('CTYPE','CUNIT','CRPIX','CRVAL','CDELT','CD1_','CD2_','PC1_','PC2_')
            wcs=WCS({k:v for k,v in hdr.items() if k.startswith(allowed)})
            scale=float(proj_plane_pixel_scales(wcs)[0]*3600)
            cx,cy=wcs.world_to_pixel_values(ra,dec)
            xs,ys=wcs.world_to_pixel_values(*coords)
            h,w=hdu.get_dims()
            sites=[(cx,cy,min(270,max(30,2*peak['rh_arcmin']*60)),
                    f'{band} · candidate centre')]
            sites.extend((xs[i],ys[i],4.,f'{band} · source {j+1}, p={prob[i]:.2f}')
                         for j,i in enumerate(strong))
            for ax,(x,y,size,title) in zip(row,sites):
                half=int(np.ceil(size/scale))
                x0,x1=max(0,int(x)-half),min(w,int(x)+half+1)
                y0,y1=max(0,int(y)-half),min(h,int(y)+half+1)
                if x0>=x1 or y0>=y1:
                    ax.set_title('Outside coadd')
                    continue
                data=hdu[y0:y1,x0:x1]
                lo,hi=np.nanpercentile(data,(8,99.5))
                extent=[(x0-.5-x)*scale,(x1-.5-x)*scale,(y0-.5-y)*scale,(y1-.5-y)*scale]
                ax.imshow(data,origin='lower',extent=extent,cmap='gray',vmin=lo,vmax=hi)
                if ax is row[0]:
                    keep=prob>.05
                    ax.scatter((xs[keep]-x)*scale,(ys[keep]-y)*scale,facecolors='none',
                               edgecolors='#68e4ff',s=20)
                ax.plot(0,0,marker='+',color='#ffbb50',ms=9)
                ax.set(xlabel='Image offset (arcsec)',title=title,xlim=(-size,size),ylim=(-size,size))
    fig.suptitle(f'LS DR11 · {ra:.5f}, {dec:+.5f} · {name}')
    fig.savefig(path,dpi=140)
    plt.close(fig)
    return True


def review(field_id, depth, group_limit=None):
    root, data_root, cfg = settings()
    if depth == 'deep':
        for b in 'gr':
            cfg[f'{b}_max'] += .5
    out = Path('results/summary') / f'{field_id}-{depth}'
    manifest = json.loads((out/'manifest.json').read_text())
    spec = manifest['field']
    bricks = load_bricks(root)
    fields = [r for r in read_csv(Path('results/summary/pilot_candidate_summary.csv'))
              if r['field_id'] == field_id and r['depth'] == depth]
    if group_limit:
        selected = set()
        for row in sorted(fields, key=lambda r: (r['branch'] != 'main', int(r['rank']))):
            selected.add(row['candidate_group_id'])
            if len(selected) == group_limit:
                break
        fields = [row for row in fields if row['candidate_group_id'] in selected]
    if not fields:
        return
    field, data, area, _ = field_cache(root, data_root, spec, cfg, bricks)
    sample, _, valid, mags, chosen = select(data, field, area, cfg)
    model = load_isochrone(data_root/'resources'/cfg['isochrone'])
    cmd = CMD(sample, model, cfg)
    tree = cKDTree(sample[:, :2])
    work = runs_path(data_root)/f'{field_id}-{depth}'
    figure_dir = Path('results/figures') / f'{field_id}-{depth}'
    summary = []
    with (work/'all_template_peaks.csv').open() as f:
        raw_peaks = [convert_peak(r) for r in csv.DictReader(f)]
    raw_xy = np.array([(r['x'],r['y']) for r in raw_peaks]).reshape(-1,2)
    raw_tree = cKDTree(raw_xy)
    for row in fields:
        peak = convert_peak(row)
        best = fit_at_peak(peak, sample, field, area, cmd)
        if best is None:
            continue
        fit_peak, fit, idx, prob, ratio = best
        ranking = np.argsort(prob)[::-1]
        for n in (1, 3):
            keep = np.ones(len(sample), dtype=bool)
            keep[idx[ranking[:n]]] = False
            reduced, _, _ = point_fit(sample[keep], cmd, field, area, fit_peak, ratio=ratio[keep])
            fit[f'C_refit_TS_without_top{n}'] = reduced['ts'] if reduced else None
        locus, _ = cmd.weights(peak['dm'])
        test = {}
        for threshold in (5, 7):
            use = locus & np.all(sample[:, 4:6] <= 2.5/np.log(10)/threshold, axis=1)
            a, b, _, _ = exact_onoff(field, peak['x'], peak['y'], peak['rh_arcmin'], tree, area, use)
            test[f'cmd_on_snr{threshold}'] = a
            test[f'cmd_off_snr{threshold}'] = b
        nearby = raw_tree.query_ball_point((fit_peak['x'],fit_peak['y']),fit_peak['rh_arcmin'])
        raw = [raw_peaks[i] for i in nearby if raw_peaks[i]['method']==peak['method']]
        total = prob.sum()
        fit['top1_membership_fraction'] = float(prob[ranking[:1]].sum()/total) if total else 0.
        fit['top3_membership_fraction'] = float(prob[ranking[:3]].sum()/total) if total else 0.
        fit['effective_members'] = float(total**2/(prob@prob)) if total else 0.
        label = f"{peak['branch']}-{peak['method']}-{peak['rank']}"
        co = manifest['observing_conditions_source_sample']
        candidate(figure_dir/f'candidate-{label}.png', spec, field, area, sample, data,
                  valid, mags, chosen, fit_peak, idx, prob, raw, model, co)
        metadata = observing_page(figure_dir/f'candidate-{label}-environment.png',
                                  root, bricks, data, valid, field, fit_peak, row)
        images = image_cutouts(figure_dir/f'candidate-{label}-images.png', root, bricks, field,
                               fit_peak,sample[idx,:2],prob)
        np.savez_compressed(work/f'membership-{label}.npz', source_ids=data[
            ['RELEASE', 'BRICKID', 'OBJID']][chosen][idx], probability=prob)
        summary.append(dict(field=field_id, depth=depth, branch=peak['branch'], method=peak['method'], rank=peak['rank'],
                            fit_dm=fit_peak['dm'], fit_rh_arcmin=fit_peak['rh_arcmin'],
                            evidence_level='L0', image_diagnostic_generated=images,
                            candidate_group_id=row['candidate_group_id'], fit_ra_deg=fit_peak['ra_deg'],
                            fit_dec_deg=fit_peak['dec_deg'], **fit, **test, **metadata))
    if summary:
        write_csv(out/'review.csv', summary)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    p.add_argument('--depth', choices=('base', 'deep'), default='base')
    p.add_argument('--group-limit',type=int)
    args = p.parse_args()
    review(args.field, args.depth, args.group_limit)
