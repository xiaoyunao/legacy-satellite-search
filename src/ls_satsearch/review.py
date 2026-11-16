"""Review retained L0 peaks with local image and catalog diagnostics on NERSC."""

import argparse
import csv
import json
from pathlib import Path

from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from .data import load_bricks, select
from .plots import candidate
from .run import field_cache, quantile, read_csv, settings, write_csv
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
    return best


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
    ax = axes[1, 1]
    valid_bricks = field.overlap(bricks['RA1'], bricks['RA2'], bricks['DEC1'], bricks['DEC2'])
    for b in bricks[valid_bricks]:
        ra, dec = peak['ra_deg'], peak['dec_deg']
        if (ra-b['RA1']) % 360 >= (b['RA2']-b['RA1']) % 360 or not b['DEC1'] <= dec < b['DEC2']:
            continue
        name = b['BRICKNAME'].strip()
        p = root / 'south/coadd' / name[:3] / name / f'legacysurvey-{name}-image.jpg'
        if p.is_file():
            with Image.open(p) as im:
                ax.imshow(im)
            ax.set_title(f'LS coadd preview · {name}')
        break
    ax.axis('off')
    nearest = row.get('nearest_known', '')
    sep = row.get('nearest_known_arcmin', '')
    fig.suptitle(f"L0 · {row['field_id']} · {peak['method']} rank {peak['rank']}\n"
                 f"Nearest cataloged object: {nearest} ({float(sep):.1f}′)" if sep else "L0 peak")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {f'{k}_local_p10_p50_p90': quantile(v) for k, v in zip(('g_depth', 'g_seeing', 'ebv'), values)}


def review(field_id, depth):
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
    if not fields:
        return
    field, data, area, _ = field_cache(root, data_root, spec, cfg, bricks)
    sample, _, valid, mags, chosen = select(data, field, area, cfg)
    model = load_isochrone(data_root/'resources'/cfg['isochrone'])
    cmd = CMD(sample, model, cfg)
    tree = cKDTree(sample[:, :2])
    work = data_root/'runs'/f'{field_id}-{depth}'
    figure_dir = Path('results/figures') / f'{field_id}-{depth}'
    summary = []
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
        # Only the candidate's local raw template peaks feed its response plot.
        with (work/'all_template_peaks.csv').open() as f:
            raw = [convert_peak(r) for r in csv.DictReader(f) if r['method'] == peak['method'] and
                   np.hypot(float(r['x'])-peak['x'], float(r['y'])-peak['y']) < fit_peak['rh_arcmin']]
        label = f"{peak['method']}-{peak['rank']}"
        co = manifest['observing_conditions_source_sample']
        candidate(figure_dir/f'candidate-{label}.png', spec, field, area, sample, data,
                  valid, mags, chosen, fit_peak, idx, prob, raw, model, co)
        metadata = observing_page(figure_dir/f'candidate-{label}-environment.png',
                                  root, bricks, data, valid, field, fit_peak, row)
        np.savez_compressed(work/f'membership-{label}.npz', source_ids=data[
            ['RELEASE', 'BRICKID', 'OBJID']][chosen][idx], probability=prob)
        summary.append(dict(field=field_id, depth=depth, method=peak['method'], rank=peak['rank'],
                            fit_dm=fit_peak['dm'], fit_rh_arcmin=fit_peak['rh_arcmin'],
                            evidence_level='L0', **fit, **test, **metadata))
    if summary:
        write_csv(out/'review.csv', summary)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    p.add_argument('--depth', choices=('base', 'deep'), default='base')
    args = p.parse_args()
    review(args.field, args.depth)
