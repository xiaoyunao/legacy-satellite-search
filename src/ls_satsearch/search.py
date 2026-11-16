"""Two independent sky scans and candidate-only point-process refits."""

from functools import lru_cache
from time import monotonic

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter, map_coordinates
from scipy.optimize import brentq
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree
from scipy.special import logsumexp, xlogy
from scipy.stats import binom


def load_isochrone(path):
    with path.open() as handle:
        for line in handle:
            if line.startswith('#') and 'int_IMF' in line and 'M_ini' in line:
                tokens = line[1:].split()
                cols = [tokens.index(key) for key in ('g', 'r', 'int_IMF')]
                break
        else:
            raise ValueError('Expected PARSEC header with g, r and integral IMF')
    g, r, integral = np.loadtxt(path, usecols=cols, unpack=True)
    weights = np.maximum(np.gradient(integral), 0)
    if not np.all(np.isfinite(g + r + weights)) or not np.any(weights > 0):
        raise ValueError('Invalid PARSEC template or IMF')
    length = np.hypot(np.diff(g), np.diff(r))
    along = np.r_[0, np.cumsum(length)]
    fine = np.linspace(0, along[-1], int(along[-1] / .015) + 2)
    return np.column_stack((g, r)), weights, np.column_stack(
        (np.interp(fine, along, g), np.interp(fine, along, r)))


class CMD:
    """Use g,r directly, where the independent-band error approximation applies."""

    def __init__(self, sample, model, cfg):
        self.mags = sample[:, 2:4]
        self.err = sample[:, 4:6]
        self.model, self.imf, self.locus = model
        self.lo, self.bin = 7, .08
        self.edges = [np.arange(self.lo, cfg[k] + self.bin, self.bin) for k in ('g_max', 'r_max')]
        self.coords = ((self.mags - self.lo) / self.bin - .5).T
        self.valid_cmd = np.all(self.mags >= self.lo, axis=1)
        self.eligible = [np.clip((cfg[k] - e[:-1]) / self.bin, 0, 1)
                         for k, e in zip(('g_max', 'r_max'), self.edges)]
        self.limit = cfg['background_tile_arcmin']
        self.error_class = np.digitize(np.max(self.err, axis=1), (.035, .075, .13))
        self.background = np.empty(len(sample))
        tile = np.floor(sample[:, :2] / self.limit).astype(int)
        for group in np.unique(tile, axis=0):
            use = np.all(tile == group, axis=1)
            nearby = np.all(abs(tile - group) <= 1, axis=1)
            for error_id in range(4):
                ids = use & (self.error_class == error_id)
                if not np.any(ids):
                    continue
                eligible = nearby & (self.error_class == error_id)
                hist, *_ = np.histogram2d(*self.mags[eligible].T, bins=self.edges)
                # The larger unstratified CMD supplies the regularizing shape.
                prior, *_ = np.histogram2d(*self.mags[nearby].T, bins=self.edges)
                prior = gaussian_filter(prior, 3) + 0.001
                prior *= 30 / prior.sum()
                density = gaussian_filter(hist, 1.5) + prior
                density *= np.outer(*self.eligible)
                density /= density.sum()
                self.background[ids] = map_coordinates(density, self.coords[:, ids], order=1, mode='nearest')

    def weights(self, dm):
        # Nearest candidates in Euclidean g,r; evaluate with source errors
        # independently in each band and allow a small model-width floor.
        delta = self.mags - dm
        distance, ids = cKDTree(self.locus).query(delta, k=16, distance_upper_bound=.52)
        residual = delta[:, None, :] - self.locus[np.minimum(ids, len(self.locus) - 1)]
        chi2 = np.sum(residual**2 / (self.err[:, None, :]**2 + .045**2), axis=2)
        on_locus = np.any((chi2 <= 2.5**2) & np.isfinite(distance), axis=1) & self.valid_cmd

        # Use an extended model grid before convolving. This includes
        # photometric scattering across both faint selection boundaries.
        padding = 14
        extended = [np.r_[e[0] - self.bin * np.arange(padding, 0, -1),
                          e, e[-1] + self.bin * np.arange(1, padding + 1)]
                    for e in self.edges]
        hist, *_ = np.histogram2d(*(self.model + dm).T, bins=extended, weights=self.imf)
        ratio = np.zeros(len(self.mags))
        for i in range(4):
            use = (self.error_class == i) & self.valid_cmd
            if not np.any(use):
                continue
            sigma = np.hypot(np.median(self.err[use], axis=0), .045) / self.bin
            density = gaussian_filter(hist, sigma, mode='constant')[padding:-padding, padding:-padding]
            density *= np.outer(*self.eligible)
            if density.sum():
                density /= density.sum()
                ratio[use] = map_coordinates(density, self.coords[:, use], order=1,
                                              mode='nearest') / self.background[use]
        return on_locus, ratio


def rebin(image, factor):
    n = len(image) // factor
    return image.reshape(n, factor, n, factor).sum(axis=(1, 3))


def convolution(image, kernel):
    return fftconvolve(image, kernel, mode='same')


@lru_cache
def kernels(rh_pixels):
    size = int(np.ceil(6 * rh_pixels))
    yy, xx = np.ogrid[-size:size + 1, -size:size + 1]
    r2 = xx * xx + yy * yy
    on = r2 <= (1.5 * rh_pixels)**2
    off = (r2 >= (3.5 * rh_pixels)**2) & (r2 <= (6 * rh_pixels)**2)
    return on, off


@lru_cache
def area_stencil(radius, step, phase_y, phase_x):
    n = int(np.ceil(6 * radius / step))
    axis = np.arange(-n, n + 1) + .5
    dist = np.hypot(axis[None, :] - phase_x, axis[:, None] - phase_y) * step
    return dist <= 1.5 * radius, (dist >= 3.5 * radius) & (dist <= 6 * radius)


def exact_onoff(field, x, y, radius, tree, coverage, on_cmd):
    sub = coverage.shape[0] // field.n
    step = field.step / sub
    iy, ix = (np.array([y, x]) + field.limit) / step
    n = int(np.ceil(6 * radius / step))
    jy, jx = int(iy), int(ix)
    stencil = area_stencil(radius, step, round(iy - jy, 8), round(ix - jx, 8))
    y0, y1 = max(0, jy - n), min(len(coverage), jy + n + 1)
    x0, x1 = max(0, jx - n), min(len(coverage), jx + n + 1)
    area = coverage[y0:y1, x0:x1]
    sy = slice(y0 - jy + n, y1 - jy + n)
    sx = slice(x0 - jx + n, x1 - jx + n)
    a_on, a_off = [np.count_nonzero(area & k[sy, sx]) * step**2 for k in stencil]
    members = np.asarray(tree.query_ball_point((x, y), 6 * radius), dtype=int)
    members = members[on_cmd[members]]
    r = np.hypot(*(tree.data[members] - (x, y)).T)
    n_on = int(np.sum(r <= 1.5 * radius))
    n_off = int(np.sum(r >= 3.5 * radius))
    return n_on, n_off, a_on, a_off


def binomial_tail_score(k, n, p):
    """Compute -log10 P(X>=k) without collapsing very small tails into ties."""
    log_tail = binom.logsf(k - 1, n, p)
    if not np.isfinite(log_tail):
        log_tail = logsumexp(binom.logpmf(np.arange(k, n + 1), n, p))
    return -float(log_tail) / np.log(10)


def scan(sample, field, coverage, model, cfg):
    started = monotonic()
    cmd = CMD(sample, model, cfg)
    common_seconds = monotonic() - started
    seconds = dict(A=0., B=0., cmd=common_seconds, shared=0.)
    iy, ix = field.pixel(*sample[:, :2].T)
    linear = iy * field.n + ix
    tree = cKDTree(sample[:, :2])
    area_high = rebin(coverage, coverage.shape[0] // field.n)
    area_high = area_high / (coverage.shape[0] // field.n)**2
    grids = []
    for radius in cfg['radii_arcmin']:
        factor = min(32, 2**int(np.floor(np.log2(radius / (3*field.step) + 1e-10))))
        step = field.step * factor
        on, off = kernels(radius / step)
        a = rebin(area_high, factor) * field.step**2
        aon, aoff = [np.maximum(convolution(a, k), 0) for k in (on, off)]
        pos = (np.arange(len(a)) + .5) * step - field.limit
        inner = abs(pos) < field.width * 30
        ok = (inner[:, None] & inner[None, :] & (a > 0) &
              (aon >= cfg['min_on_fraction'] * on.sum() * step**2) &
              (aoff >= cfg['min_off_fraction'] * off.sum() * step**2))
        p = np.divide(aon, aon + aoff, out=np.full_like(aon, .5), where=ok)
        alpha = np.divide(aon, aoff, out=np.zeros_like(aon), where=ok)
        grids.append((factor, radius, on, off, aon, aoff, pos, ok, p, alpha))
    seconds['shared'] += monotonic() - started - common_seconds

    peaks = []
    dm0, dm1, delta = cfg['dm']
    for dm in np.arange(dm0, dm1 + delta / 2, delta):
        started = monotonic()
        selected, ratio = cmd.weights(dm)
        weight = np.minimum(ratio, 25.)
        images = [np.bincount(linear, weights=w, minlength=field.n**2).reshape(field.n, field.n)
                  for w in (selected, weight, weight**2)]
        seconds['cmd'] += monotonic() - started
        for factor, radius, on, off, aon, aoff, pos, ok, p, alpha in grids:
            started = monotonic()
            count = rebin(images[0], factor)
            ni, no = [np.rint(convolution(count, k)).clip(0) for k in (on, off)]
            nt = ni + no
            expect = nt * p
            deviance = 2 * (xlogy(ni, (ni + 1e-15) / (expect + 1e-15)) +
                            xlogy(no, (no + 1e-15) / (nt - expect + 1e-15)))
            a_score = np.sqrt(np.maximum(deviance, 0))
            a_score[(ni <= expect) | (ni < 3)] = 0
            for i, j in maxima(a_score, ok, cfg['peak_seed_floor']):
                x, y = pos[j], pos[i]
                n_on, n_off, area_on, area_off = exact_onoff(
                    field, x, y, radius, tree, coverage, selected)
                if (area_on < cfg['min_on_fraction'] * np.pi * (1.5 * radius)**2 or
                        area_off < cfg['min_off_fraction'] * np.pi * (6**2 - 3.5**2) * radius**2):
                    continue
                prob = area_on / (area_on + area_off)
                score = binomial_tail_score(n_on, n_on + n_off, prob)
                peaks.append(dict(method='A', x=x, y=y, dm=dm, rh_arcmin=radius,
                                  score=score, n_on=n_on, n_off=n_off,
                                  area_on_arcmin2=area_on, area_off_arcmin2=area_off))
            seconds['A'] += monotonic() - started
            started = monotonic()
            weighted, squared = [rebin(im, factor) for im in images[1:]]
            wi, wo = [convolution(weighted, k) for k in (on, off)]
            var_off = np.maximum(convolution(squared, off), 0)
            # Regularize local variance of the compensated weighted aperture.
            global_v = squared.sum() / max(area_high.sum() * field.step**2, 1)
            var_density = (var_off + 15 * global_v) / (aoff + 15)
            variance = (aon + alpha**2 * aoff) * var_density
            b_score = (wi - alpha * wo) / np.sqrt(np.maximum(variance, 1))
            b_score[convolution(rebin((images[1] > 0).astype(float), factor), on) < 2.5] = 0
            for i, j in maxima(b_score, ok, cfg['peak_seed_floor']):
                peaks.append(dict(method='B', x=pos[j], y=pos[i], dm=dm, rh_arcmin=radius,
                                  score=b_score[i, j], weighted_on=wi[i, j], weighted_off=wo[i, j],
                                  area_on_arcmin2=aon[i, j], area_off_arcmin2=aoff[i, j]))
            seconds['B'] += monotonic() - started
    for i, peak in enumerate(peaks):
        peak['raw_peak_id'] = i + 1
        peak['ra_deg'], peak['dec_deg'] = field.sky(peak['x'], peak['y'])
    return peaks, deduplicate(peaks), seconds, cmd


def maxima(score, ok, floor):
    selected = ok & np.isfinite(score) & (score >= floor)
    image = np.where(ok, score, -np.inf)
    return np.argwhere(selected & (image == maximum_filter(image, size=3, mode='constant', cval=-np.inf)))


def deduplicate(peaks):
    result = []
    for method in ('A', 'B'):
        rows = sorted((p for p in peaks if p['method'] == method),
                      key=lambda p: (-p['score'], p['dm'], p['rh_arcmin'], p['x'], p['y']))
        if not rows:
            continue
        xy = np.array([(r['x'], r['y']) for r in rows])
        tree = cKDTree(xy)
        rh = np.array([r['rh_arcmin'] for r in rows])
        assigned = np.zeros(len(rows), dtype=int)
        rank = 0
        for i, row in enumerate(rows):
            if not assigned[i]:
                rank += 1
                nearby = np.array(tree.query_ball_point(xy[i], max(.5, .75 * rh.max())))
                dist = np.linalg.norm(xy[nearby] - xy[i], axis=1)
                use = (assigned[nearby] == 0) & (dist <= np.maximum(.5, .75 * np.maximum(rh[i], rh[nearby])))
                assigned[nearby[use]] = rank
                result.append(dict(row, rank=rank))
            row['dedup_rank'] = int(assigned[i])
    return result


def point_fit(sample, cmd, field, coverage, peak, radius=None, ratio=None):
    """Refit richness at a proposed sky/DM/size point with a masked Plummer.

    The background density is measured in an annulus. Richness counts expected
    selected stars over the unmasked infinite Plummer profile.
    """
    x, y, dm = (peak[k] for k in ('x', 'y', 'dm'))
    rh = peak['rh_arcmin'] if radius is None else radius
    if ratio is None:
        _, ratio = cmd.weights(dm)
    rr = np.hypot(sample[:, 0] - x, sample[:, 1] - y)
    local = rr <= 3.5 * rh
    sub = coverage.shape[0] // field.n
    step = field.step / sub
    axis = (np.arange(len(coverage)) + .5) * step - field.limit
    ix = np.flatnonzero(abs(axis - x) <= 6 * rh)
    iy = np.flatnonzero(abs(axis - y) <= 6 * rh)
    r_area = np.hypot(axis[ix][None, :] - x, axis[iy][:, None] - y)
    good = coverage[np.ix_(iy, ix)]
    outer = (r_area > 3.5 * rh) & (r_area <= 6 * rh)
    area_off = np.sum(good & outer) * step**2
    observed = np.sum((rr > 3.5 * rh) & (rr <= 6 * rh))
    if area_off == 0 or observed < 5:
        return None, np.flatnonzero(local), np.zeros(local.sum())
    background = observed / area_off
    spatial = lambda r: (1 + (r / rh)**2)**-2 / (np.pi * rh**2)
    integr = np.sum(spatial(r_area)[good & (r_area <= 3.5 * rh)]) * step**2
    contrast = spatial(rr[local]) * ratio[local] / background
    strength = 0.
    if contrast.sum() > integr > 0:
        strength = brentq(lambda s: np.sum(contrast / (1 + s * contrast)) - integr,
                          0, (len(contrast) + 1) / integr)
    low = np.log1p(strength * contrast).sum() - strength * integr
    prob = strength * contrast / (1 + strength * contrast)
    return dict(ts=2 * low, richness=strength, profile_integral=integr,
                bg_per_arcmin2=background, n_local=int(local.sum())), np.flatnonzero(local), prob
