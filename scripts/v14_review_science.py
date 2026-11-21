"""Render DES-style six-panel diagnostics from original catalogues and saved fits."""

import argparse
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.ticker import MaxNLocator
import numpy as np
from scipy.stats import chi2

from ls_satsearch.data import select
from ls_satsearch.paper_diagnostic import histogram, smooth_density, usable_centers
from ls_satsearch.run import field_cache, read_csv, sha, write_json
from ls_satsearch.search import CMD, load_isochrone
from scripts.v14_review_integrity import verify


def label(ax, text):
    ax.text(.035, .965, text, va='top', transform=ax.transAxes, fontsize=11,
            bbox=dict(facecolor='white', edgecolor='0.25', pad=3))


def sky_axes(ax, half):
    ax.set(xlim=(half / 60, -half / 60), ylim=(-half / 60, half / 60),
           xlabel=r'$\Delta$ East (deg)', ylabel=r'$\Delta$ North (deg)', aspect='equal')
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.yaxis.set_major_locator(MaxNLocator(5))


def data_for_field(scan):
    root, data = (Path(os.environ[k]) for k in ('LS_DR11_ROOT', 'LS_SAT_DATA'))
    cfg = scan['config']
    template = data / 'resources' / cfg['isochrone']
    if scan['status'] != 'complete' or sha(template) != scan['model_sha256']:
        raise ValueError('Require the original complete scan and stellar template')
    field, raw, area, _ = field_cache(root, data, scan['field'], cfg, None)
    sample, _, valid, mags, chosen = select(raw, field, area, cfg)
    extended = valid & np.isin(np.char.strip(raw['TYPE'].astype('U')), ('REX', 'EXP', 'DEV', 'SER'))
    ext = raw[extended]
    errors = np.column_stack([2.5 / np.log(10) / (ext[f'FLUX_{b}'] * np.sqrt(ext[f'FLUX_IVAR_{b}']))
                             for b in 'GR'])
    galaxies = np.column_stack((*field.xy(ext['RA'], ext['DEC']), mags[extended], errors))
    return field, area, sample, galaxies, raw[['RELEASE', 'BRICKID', 'OBJID']][chosen], load_isochrone(template)[2]


def render(path, field, area, sample, galaxies, locus, mode, members, prob, sigma, title=None,
           g_limit=23.5):
    """Use the same spatial support and CMD filter for stars and extended sources."""
    if (title is None) != (members is None and prob is None):
        raise ValueError('Only the held layout accepts membership evidence')
    x0, y0 = field.xy(float(mode['fit_ra_deg']), float(mode['fit_dec_deg']))
    dm, rh = float(mode['fit_dm']), float(mode['fit_rh_arcmin'])
    half = max(8., min(60., 7 * rh))
    step = min(.25, sigma / 3)
    n = int(np.ceil((half + 4 * sigma) / step))
    edges = np.arange(-n, n + 1) * step
    sky, cell = usable_centers(field, area, x0, y0, edges[-1])
    geom = histogram(sky, edges) * cell
    delta = sample[:, :2] - (x0, y0)
    ext = galaxies[:, :2] - (x0, y0)
    selected = CMD.top_hat(sample[:, 2:4], sample[:, 4:6], dm, locus)
    selected_ext = CMD.top_hat(galaxies[:, 2:4], galaxies[:, 4:6], dm, locus)
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.4), layout='constrained')
    fig.set_facecolor('white')
    cmap = plt.get_cmap('Greys').with_extremes(bad='#e4e7e9')
    mids = (edges[1:] + edges[:-1]) / 2
    display = np.outer(abs(mids) <= half, abs(mids) <= half)
    map_stats = []
    for ax, points, text in zip(axes[:, 0], (delta[selected], ext[selected_ext]),
                                ('Filtered stars', 'Filtered extended sources')):
        counts = histogram(points, edges)
        density = smooth_density(counts, geom, sigma / step, step**2)
        values = density[display & np.isfinite(density)]
        upper = max(.02, float(np.quantile(values, .998))) if len(values) else .02
        extent = np.array([edges[0], edges[-1], edges[0], edges[-1]]) / 60
        artist = ax.imshow(density, extent=extent, origin='lower', cmap=cmap,
                           norm=PowerNorm(1.6, vmin=0, vmax=upper, clip=True), interpolation='nearest')
        sky_axes(ax, half)
        label(ax, f'{text} · σ = {sigma:g}′')
        fig.colorbar(artist, ax=ax, label=r'arcmin$^{-2}$', shrink=.88)
        map_stats.append(dict(display_count=int(counts[display].sum()), finite_bins=len(values)))

    if edges[-1] < 6 * rh:
        sky, _ = usable_centers(field, area, x0, y0, 6 * rh)
    rr, rg, ra = (np.hypot(*p.T) for p in (delta, ext, sky))
    radial = axes[0, 1]
    rb = np.r_[0, np.geomspace(.4 * rh, 6 * rh, 11)]
    ar = np.histogram(ra, rb)[0] * cell
    good = ar > 0
    for radius, color, name in ((rr, '0.56', 'All selected stars'),
                                (rr[selected], '#b33139', 'CMD-filtered stars'),
                                (rg[selected_ext], '0.15', 'CMD-filtered extended sources')):
        count = np.histogram(radius, rb)[0][good]
        lo = np.where(count > 0, chi2.ppf(.15865, 2 * np.maximum(count, 1)) / 2, 0.)
        hi = chi2.ppf(.84135, 2 * (count + 1)) / 2
        radial.errorbar(((rb[1:] + rb[:-1]) / 2)[good], count / ar[good],
                        yerr=[(count - lo) / ar[good], (hi - count) / ar[good]],
                        fmt='o-', ms=3.1, lw=.9, color=color, label=name)
    if title is not None:
        r = np.linspace(0, 6 * rh, 160)
        bg = float(mode['bg_per_arcmin2'])
        density = float(mode['richness']) / (np.pi * rh**2 * (1 + (r / rh)**2)**2)
        radial.plot(r, bg + density, lw=1.1, color='#254f93', label='Saved Plummer + background')
        radial.axhline(bg, ls=':', lw=1., color='#254f93')
    radial.set(xlim=(0, 6 * rh), ylim=(0, None), xlabel='Radius (arcmin)',
               ylabel=r'Density (arcmin$^{-2}$)')
    radial.legend(loc='upper right', frameon=False, fontsize=8)

    core, off = rr <= 1.5 * rh, (rr >= 3.5 * rh) & (rr <= 6 * rh)
    a_on = (ra <= 1.5 * rh).sum() * cell
    a_off = ((ra >= 3.5 * rh) & (ra <= 6 * rh)).sum() * cell
    color = sample[:, 2] - sample[:, 3]
    mag = sample[:, 2]
    cb, gb = np.linspace(-.45, 1.15, 30), np.linspace(16., g_limit + .1, 36)
    ax_cmd, sky_zoom, probability_cmd = axes[1, 1], axes[0, 2], axes[1, 2]
    if a_off:
        hess = np.histogram2d(mag[off], color[off], bins=(gb, cb))[0] * a_on / a_off
        ax_cmd.imshow(np.log1p(hess), extent=(cb[0], cb[-1], gb[0], gb[-1]), origin='lower',
                      cmap='Greys', aspect='auto', alpha=.42, interpolation='nearest')
    ax_cmd.scatter(color[core], mag[core], s=8, color='#b33139', alpha=.78, linewidths=0)
    label(ax_cmd, f'Core CMD · r ≤ {1.5 * rh:.1f}′')
    if a_off:
        ax_cmd.text(.035, .04, 'Gray: area-scaled background', transform=ax_cmd.transAxes,
                    fontsize=8, color='0.33')

    zoom = max(4., 3.5 * rh)
    sky_inside = np.max(abs(delta), axis=1) <= zoom
    sky_zoom.scatter(*(delta[sky_inside].T / 60), s=4, color='0.72', linewidths=0)
    probability_cmd.scatter(color[sky_inside], mag[sky_inside], s=4, color='0.75', linewidths=0)
    if title is None:
        use = selected & sky_inside
        sky_zoom.scatter(*(delta[use].T / 60), s=9, color='#254f93', linewidths=0)
        probability_cmd.scatter(color[use], mag[use], s=9, color='#254f93', linewidths=0)
        label(sky_zoom, 'CMD-filtered positions')
        label(probability_cmd, 'CMD-filtered stars')
    else:
        good_p = np.flatnonzero((prob >= .05) & sky_inside[members])
        order = good_p[np.argsort(prob[good_p])]
        idx = members[order]
        colors = dict(c=prob[order], cmap='viridis', vmin=0, vmax=1, s=15, linewidths=.18,
                      edgecolors='0.18')
        points = sky_zoom.scatter(*(delta[idx].T / 60), **colors)
        probability_cmd.scatter(color[idx], mag[idx], **colors)
        fig.colorbar(points, ax=axes[:, 2], label='C membership probability (p ≥ 0.05)', shrink=.82)
        label(sky_zoom, 'Stellar positions')
        label(probability_cmd, 'Membership CMD')
    sky_axes(sky_zoom, zoom)
    track = np.column_stack((locus[:, 0] - locus[:, 1], locus[:, 0] + dm))
    breaks = np.flatnonzero(np.linalg.norm(np.diff(locus, axis=0), axis=1) > .08) + 1
    for ax in (ax_cmd, probability_cmd):
        for segment in np.split(track, breaks):
            ax.plot(*segment.T, color='#152644', lw=.95)
        ax.set(xlim=(cb[0], cb[-1]), ylim=(gb[-1], gb[0]), xlabel=r'$(g-r)_0$ (mag)',
               ylabel=r'$g_0$ (mag)')
    if title is not None:
        fig.suptitle(f'{title}  ·  DR11  ·  μ = {dm:.2f} mag  ·  rₕ = {rh:.2f}′', fontsize=15)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return dict(display_sigma_arcmin=sigma, maps=map_stats, core_area_arcmin2=float(a_on),
                annulus_area_arcmin2=float(a_off), core_psf_count=int(core.sum()),
                core_cmd_count=int((core & selected).sum()), saved_C_plotted=title is not None)


def saved_members(membership, mode, selected_ids):
    with np.load(membership, allow_pickle=False) as saved:
        ids, prob = saved['source_ids'], saved['probability']
    integrity = verify(mode, ids, prob)
    lookup = {tuple(key): idx for idx, key in enumerate(selected_ids)}
    members = np.array([lookup[tuple(key)] for key in ids], dtype=int)
    return members, prob, integrity


def hercules(output):
    data = Path(os.environ['LS_SAT_DATA'])
    manifest = Path('../holdout-v4/results/summary/fresh_06-base/manifest.json')
    fits = Path('results/v4/holdout/group_review_modes.csv')
    group = 'fresh_06-A_base-0.3-001'
    modes = [r for r in read_csv(fits) if r['candidate_group_id'] == group and r['fit_status'] == 'complete']
    mode = max(modes, key=lambda r: float(r['ts']))
    membership = data / 'runs/v4/fresh_06-base' / f"membership-main-A-{mode['rank']}.npz"
    scan = json.loads(manifest.read_text())
    field, area, sample, galaxies, ids, locus = data_for_field(scan)
    members, prob, integrity = saved_members(membership, mode, ids)
    output.mkdir(parents=True, exist_ok=False)
    result = {}
    for sigma in (.5, 2.):
        path = output / f'hercules_sigma{sigma:g}.png'
        metrics = render(path, field, area, sample, galaxies, locus, mode, members, prob, sigma,
                         title='Hercules', g_limit=scan['config']['g_max'])
        result[path.name] = dict(metrics, sha256=sha(path))
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'],
               source_scan_sha256=sha(manifest), source_C_sha256=sha(fits), membership_sha256=sha(membership),
               renderer_sha256=sha(Path(__file__)), membership_integrity=integrity, outputs=result,
               scope='Known-control layout preview from a saved C fit. No refit or new detection.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use NERSC compute CPUs for catalogue work')
    hercules(args.output)
