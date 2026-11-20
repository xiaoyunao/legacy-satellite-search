"""Aggregate diagnostics for coverage, controls, and high-ranked peaks."""

import matplotlib.pyplot as plt
import numpy as np


def overview(path, field, area, sample, spec, cfg, model):
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.5), layout='constrained')
    lim = field.limit / 60
    ax[0].imshow(area, origin='lower', extent=[-lim, lim, -lim, lim], cmap='cividis',
                 vmin=0, vmax=1, interpolation='nearest')
    w = field.width / 2
    ax[0].add_patch(plt.Rectangle((-w, -w), 2*w, 2*w, fill=False, color='orange', lw=1.3))
    ax[0].set(xlabel='East (deg)', ylabel='North (deg)', title='Usable exposure and analysis region')
    inner = np.max(abs(sample[:, :2]), axis=1) < w*60
    g, r = sample[inner, 2:4].T
    ax[1].hist2d(g-r, g, bins=(125, 130), range=((-1, 2.5), (13, cfg['g_max'])), cmin=1, cmap='magma')
    ax[1].set(xlabel='$(g-r)_0$ (mag)', ylabel='$g_0$ (mag)', title=f'{int(inner.sum()):,} selected point sources')
    ax[1].invert_yaxis()
    fig.suptitle(spec['id'])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def candidate(path, spec, field, area, sample, sources, valid, mags, chosen, peak, idx, prob, raw, model, conditions):
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), layout='constrained')
    x, y, dm, rh = (peak[k] for k in ('x', 'y', 'dm', 'rh_arcmin'))
    lim = 6 * rh
    delta = sample[:, :2] - (x, y)
    rr = np.hypot(*delta.T)
    near = rr < lim
    ax = axes[0, 0]
    ax.hist2d(*delta[near].T, bins=25, range=[[-lim, lim]]*2, cmap='Greys')
    ax.scatter(*delta[idx].T, s=18, c=prob, cmap='plasma', vmin=0, vmax=1, alpha=.8)
    ax.add_patch(plt.Circle((0, 0), rh, color='tab:blue', fill=False))
    ax.set(xlabel='East (arcmin)', ylabel='North (arcmin)', title='Density and C membership')
    ax.set_aspect('equal')
    annulus = (rr > 3.5 * rh) & (rr < np.sqrt(3.5**2 + 1.5**2)*rh)
    locus = model[0]
    for axis, selection, title in zip(axes[0, 1:], (rr <= 1.5 * rh, annulus),
                                      ('Central CMD', 'Equal geometric area annulus CMD')):
        g, r = sample[selection, 2:4].T
        axis.scatter(g-r, g, s=8, alpha=.6)
        # Do not connect distinct evolutionary phases across the RGB/HB handoff.
        axis.plot(locus[:, 0]-locus[:, 1], locus[:, 0]+dm, '.', color='tab:red', ms=1.5)
        axis.set(xlim=(-.5, 1.8), ylim=(max(23.5, g.max(initial=23.5)), 15), xlabel='$(g-r)_0$ (mag)',
                 ylabel='$g_0$ (mag)', title=f'{title} ({len(g)})')
    ax = axes[1, 0]
    rs = np.linspace(0, 6 * rh, 20)
    for mask, label in [(valid & chosen, 'PSF'), (valid & ~chosen, 'non-PSF')]:
        sx, sy = field.xy(sources['RA'][mask], sources['DEC'][mask])
        dist = np.hypot(sx-x, sy-y)
        sub = area.shape[0] // field.n
        step = field.step / sub
        axis = (np.arange(len(area)) + .5) * step - field.limit
        ia, ja = (np.flatnonzero(abs(axis - q) <= rs[-1]) for q in (x, y))
        rr_area = np.hypot(axis[ia][None, :] - x, axis[ja][:, None] - y)
        an = np.histogram(rr_area[area[np.ix_(ja, ia)]], bins=rs)[0] * step**2
        nn = np.histogram(dist, bins=rs)[0]
        ax.plot((rs[:-1]+rs[1:])/2, np.divide(nn, an, out=np.full_like(an, np.nan), where=an > 0), '.-', label=label)
    ax.set(xlabel='Radius (arcmin)', ylabel='Sources per arcmin²', title='Masked radial profile')
    ax.legend()
    ax = axes[1, 1]
    nearby = [p for p in raw if p['method'] == peak['method'] and np.hypot(p['x']-x,p['y']-y) < rh]
    by_dm = {}
    for p in nearby:
        by_dm[p['dm']] = max(p['score'],by_dm.get(p['dm'],-np.inf))
    if by_dm:
        points = np.array(sorted(by_dm.items()))
        ax.plot(*points.T, '.-')
    ax.set(xlabel='Distance modulus (mag)', ylabel=f"Method {peak['method']} score", title='Nearby template peaks')
    ax = axes[1, 2]
    n = len(area)
    sc = n / (2 * field.limit)
    def pixel(coord):
        return int(np.clip((coord + field.limit) * sc, 0, n))
    i, j, k, l = pixel(x-lim), pixel(x+lim), pixel(y-lim), pixel(y+lim)
    extent = [i/sc-field.limit-x, j/sc-field.limit-x, k/sc-field.limit-y, l/sc-field.limit-y]
    ax.imshow(area[k:l, i:j], origin='lower', extent=extent, cmap='cividis',
              vmin=0, vmax=1, interpolation='nearest')
    ax.set(xlabel='East (arcmin)', ylabel='North (arcmin)', title='Local gr mask (yellow is usable)')
    fig.suptitle(f"{spec['id']} · {peak['method']} rank {peak['rank']} · "
                 f"({peak['ra_deg']:.4f}, {peak['dec_deg']:.4f}) · DM {dm:.2f} · "
                 f"$r_h$ {rh:.2f}′")
    fig.savefig(path, dpi=140)
    plt.close(fig)
