"""Run a fixed-field scan and write per-run provenance and aggregate diagnostics."""

import argparse
import csv
import fcntl
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
from time import monotonic

import numpy as np
import yaml
from astropy.coordinates import SkyCoord

from .data import Field, load_bricks, make_area, select, sweeps
from .search import exact_onoff, load_isochrone, point_fit, scan


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, value):
    def convert(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)

    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=convert, allow_nan=False) + '\n')
    tmp.replace(path)


def write_csv(path, rows, keys=()):
    fields = list(dict.fromkeys([*keys, *(k for row in rows for k in row)]))
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', newline='') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def settings():
    root = Path(os.environ['LS_DR11_ROOT'])
    data = Path(os.environ['LS_SAT_DATA'])
    return root, data, yaml.safe_load(config_path('search.yaml').read_text())


def config_path(name):
    return Path(os.environ.get('LS_SAT_CONFIG_DIR', 'configs')) / name


def associated(peak, truth, config):
    position = SkyCoord(peak['ra_deg'], peak['dec_deg'], unit='deg')
    target = SkyCoord(float(truth['ra_deg']), float(truth['dec_deg']), unit='deg')
    sep = position.separation(target).arcmin
    rh = float(truth['theta_h_arcmin'])
    dm = 5 * np.log10(float(truth['D_kpc'])) + 10
    ok = (sep <= max(config['match_min_arcmin'], config['match_rh_factor'] * rh) and
          abs(peak['dm'] - dm) <= config['match_dm_tolerance'])
    return ok, dict(offset_arcmin=sep, offset_over_rh=sep / rh, delta_dm=peak['dm'] - dm,
                    distance_error_kpc=10**((peak['dm'] - 10) / 5) - float(truth['D_kpc']))


def coverage_metrics(field, area, cfg, limit=None, center=(0, 0)):
    cell = field.step / cfg['coverage_subdivision']
    axis = (np.arange(len(area)) + .5) * cell - field.limit
    if limit is None:
        inner = np.flatnonzero(abs(axis) < field.width * 30)
        sub = area[np.ix_(inner, inner)]
        return float(sub.sum() * (cell / 60)**2), float(sub.mean())
    x, y = center
    ix = np.flatnonzero(abs(axis - x) <= limit)
    iy = np.flatnonzero(abs(axis - y) <= limit)
    inside = (axis[ix][None, :] - x)**2 + (axis[iy][:, None] - y)**2 <= limit**2
    return float((inside & area[np.ix_(iy, ix)]).sum() / inside.sum()) if inside.any() else 0.


def quantile(x):
    x = x[np.isfinite(x)]
    return np.percentile(x, [10, 50, 90]).tolist() if len(x) else None


def recovery(rows, truth, field, coverage, cfg, depth):
    records = []
    x, y = field.xy(float(truth['ra_deg']), float(truth['dec_deg']))
    radius = max(.5, float(truth['theta_h_arcmin']))
    fraction = coverage_metrics(field, coverage, cfg, 1.5 * radius, (x, y))
    off_limit = 6 * radius
    cell = field.step / cfg['coverage_subdivision']
    axis = (np.arange(len(coverage)) + .5) * cell - field.limit
    ix, iy = (np.flatnonzero(abs(axis - q) <= off_limit) for q in (x, y))
    rad = np.hypot(axis[ix][None, :] - x, axis[iy][:, None] - y)
    ring = (rad >= 3.5 * radius) & (rad <= off_limit)
    off_fraction = float((ring & coverage[np.ix_(iy, ix)]).sum() / ring.sum()) if ring.any() else 0.
    covered = fraction >= cfg['min_on_fraction'] and off_fraction >= cfg['min_off_fraction']
    for method in ('A', 'B'):
        record = dict(name=truth['name'], method=method, depth=depth, covered=covered,
                      core_valid_fraction=fraction, off_valid_fraction=off_fraction,
                      entered_peak_table=False, truth_dm=5 * np.log10(float(truth['D_kpc'])) + 10,
                      scale_below_grid=float(truth['theta_h_arcmin']) < min(cfg['radii_arcmin']))
        if covered:
            pos = SkyCoord(float(truth['ra_deg']), float(truth['dec_deg']), unit='deg')
            peers = [r for r in rows if r['method'] == method]
            if peers:
                coords = SkyCoord([r['ra_deg'] for r in peers], [r['dec_deg'] for r in peers], unit='deg')
                sep = pos.separation(coords).arcmin
                indices = np.flatnonzero((sep <= max(cfg['match_min_arcmin'], radius)) &
                                         (abs(np.array([r['dm'] for r in peers]) - record['truth_dm'])
                                          <= cfg['match_dm_tolerance']))
                if len(indices):
                    best = peers[indices[0]]
                    _, metrics = associated(best, truth, cfg)
                    record.update(entered_peak_table=True, rank=best['rank'], score=best['score'],
                                  recovered_dm=best['dm'], recovered_rh_arcmin=best['rh_arcmin'], **metrics)
            if not record['entered_peak_table']:
                record['failure_reason'] = 'no de-duplicated peak inside position and DM match tolerances'
        else:
            record['failure_reason'] = 'insufficient usable area at the fixed diagnostic aperture'
        records.append(record)
    return records


def field_cache(root, data_root, spec, cfg, bricks):
    from .fields import Census

    field = Field(spec['ra'], spec['dec'], spec['width'], min(cfg['radii_arcmin']) / 3)
    key = dict(geometry=[field.ra, field.dec, field.width, field.step, field.buffer],
               mask=cfg['reject_maskbits'], subdivision=cfg['coverage_subdivision'],
               census=spec.get('survey'), root=str(root))
    cache = data_root / 'cache' / f"{spec['id']}-{hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]}"
    cache.mkdir(exist_ok=True, parents=True)
    xs = cache / 'catalog.npy'
    ar = cache / 'coverage.npy'
    info_path = cache / 'inputs.json'
    with (cache / 'prepare.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if info_path.exists() and xs.exists() and ar.exists():
            return field, np.load(xs, allow_pickle=False), np.load(ar, allow_pickle=False), json.loads(info_path.read_text())
        sources, provenance = sweeps(root, field)
        survey = spec.get('survey')
        coverage, mask_info = make_area(root, field, bricks, sum(1 << bit for bit in cfg['reject_maskbits']),
                                       cfg['coverage_subdivision'],
                                       Census(data_root) if survey else None, survey)
        info = {**provenance, **mask_info, **key}
        np.save(xs, sources, allow_pickle=False)
        np.save(ar, coverage, allow_pickle=False)
        write_json(info_path, info)
        return field, sources, coverage, info


def execute(spec, root, data_root, cfg, bricks, template, depth, tag):
    begin = monotonic()
    field, sources, area, info = field_cache(root, data_root, spec, cfg, bricks)
    io_time = monotonic() - begin
    name = f"{spec['id']}-{depth}{tag}"
    summary = Path('results/summary') / name
    figures = Path('results/figures') / name
    work = data_root / 'runs' / name
    for path in (summary, figures, work):
        path.mkdir(exist_ok=True, parents=True)
    sample, cutflow, valid, mags, chosen = select(sources, field, area, cfg)
    effective_area, frac = coverage_metrics(field, area, cfg)
    x, y = field.xy(sources['RA'], sources['DEC'])
    inner = (abs(x) < field.width * 30) & (abs(y) < field.width * 30)
    co = {b: {} for b in 'GR'}
    for b in co:
        selected = chosen & inner
        dp = sources[f'PSFDEPTH_{b}'][selected]
        trans = sources[f'MW_TRANSMISSION_{b}'][selected]
        positive = np.isfinite(dp) & (dp > 0)
        co[b]['depth5_dered'] = quantile(22.5 - 2.5 * np.log10(5 / np.sqrt(dp[positive])) +
                                      2.5 * np.log10(trans[positive]))
        co[b]['seeing'] = quantile(sources[f'PSFSIZE_{b}'][selected])
    co['ebv'] = quantile(sources['EBV'][valid & inner]) if 'EBV' in sources.dtype.names else None
    cutflow['inner_psf'] = int((chosen & inner).sum())
    cutflow['inner_other'] = int((valid & ~chosen & inner).sum())
    cutflow['inner_psf_faint'] = int((chosen & inner & (mags[:, 0] > 22.5)).sum())
    cutflow['inner_other_faint'] = int((valid & ~chosen & inner & (mags[:, 0] > 22.5)).sum())
    print(f"{name}: area={effective_area:.3f} deg2; selected={len(sample)}; scanning", flush=True)
    manifest = dict(field=spec, bandpass='DECam g,r', release='DR11 south',
                    source_release_codes=np.unique(sources['RELEASE']).tolist(),
                    config=cfg, config_hash=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
                    fields_sha256=sha(config_path('fields.yaml')), seed=cfg['seed'], depth=depth,
                    versions={p: version(p) for p in ('numpy', 'scipy', 'fitsio', 'astropy', 'astropy-healpix',
                                                       'matplotlib', 'pyyaml')},
                    code_sha256={p.name: sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
                    model_sha256=sha(data_root / 'resources' / cfg['isochrone']),
                    slurm_job_id=os.environ.get('SLURM_JOB_ID'), area_deg2=effective_area,
                    area_fraction=frac, inputs=info, observing_conditions_source_sample=co,
                    cutflow=cutflow, io_seconds=io_time, status='prepared')
    write_json(summary / 'manifest.json', manifest)
    from .plots import overview, candidate

    overview(figures / 'coverage_cmd.png', field, area, sample, spec, cfg, template)
    if not len(sample) or not effective_area:
        manifest['status'] = 'no_usable_gr'
        if spec.get('truth'):
            truth = next(b for b in read_csv(Path('references/benchmarks.csv')) if b['name'] == spec['truth'])
            rows = recovery([], truth, field, area, cfg, depth)
            for row in rows:
                row.update(covered=False, failure_reason='no usable search sample')
            write_csv(summary / 'recovery.csv', rows)
        write_json(summary / 'manifest.json', manifest)
        return
    raw, peaks, seconds, cmd = scan(sample, field, area, template, cfg)
    write_csv(work / 'all_template_peaks.csv', raw)
    write_csv(summary / 'deduplicated_peaks.csv', peaks)
    if spec.get('truth'):
        truth = next(b for b in read_csv(Path('references/benchmarks.csv')) if b['name'] == spec['truth'])
        records = recovery(peaks, truth, field, area, cfg, depth)
        write_csv(summary / 'recovery.csv', records)
        if any(r['covered'] and not r['entered_peak_table'] for r in records):
            x0, y0 = field.xy(float(truth['ra_deg']), float(truth['dec_deg']))
            best = dict(x=x0, y=y0, dm=records[0]['truth_dm'], rh_arcmin=float(truth['theta_h_arcmin']))
            selected, ratio = cmd.weights(best['dm'])
            from scipy.spatial import cKDTree
            n1, n2, a1, a2 = exact_onoff(field, x0, y0, best['rh_arcmin'], cKDTree(sample[:, :2]), area, selected)
            fit, _, _ = point_fit(sample, cmd, field, area, best, ratio=ratio)
            write_csv(summary / 'forced_fit.csv', [dict(name=truth['name'], depth=depth, dm=best['dm'],
                      rh_arcmin=best['rh_arcmin'], n_on=n1, n_off=n2, area_on=a1, area_off=a2, **(fit or {}))])
    results = []
    for peak in [p for p in peaks if p['rank'] <= 2]:
        refit = None
        for delta in (-.25, 0., .25):
            dm = peak['dm'] + delta
            trial = dict(peak, dm=dm)
            _, ratio = cmd.weights(dm)
            for factor in (.7, 1., 1.4):
                rh = trial['rh_arcmin'] * factor
                fit, indices, prob = point_fit(sample, cmd, field, area, trial, radius=rh, ratio=ratio)
                if fit and (refit is None or fit['ts'] > refit[0]['ts']):
                    refit = (dict(fit, fit_dm=dm, fit_rh_arcmin=rh), indices, prob)
        if refit is None:
            continue
        fit, idx, prob = refit
        fit_peak = dict(peak, dm=fit['fit_dm'], rh_arcmin=fit['fit_rh_arcmin'])
        strongest = np.argsort(prob)[-3:][::-1]
        fit['max_member_probability'] = np.max(prob, initial=0.)
        fit['fixed_fit_ts_drop_top3'] = -2 * np.log1p(-np.minimum(prob[strongest], 1 - 1e-12)).sum()
        results.append({**peak, **fit})
        suffix = f"{peak['method']}-{peak['rank']}"
        np.savez_compressed(work / f'membership-{suffix}.npz', source_ids=sources[
            ['RELEASE', 'BRICKID', 'OBJID']][chosen][idx], probability=prob)
        candidate(figures / f'candidate-{suffix}.png', spec, field, area, sample, sources, valid,
                  mags, chosen, fit_peak, idx, prob, raw, template, co)
    write_csv(summary / 'candidate_refits.csv', results)
    manifest.update(status='complete', scan_seconds=seconds, wall_seconds=monotonic() - begin,
                    raw_peaks=len(raw), deduplicated_peaks=len(peaks))
    write_json(summary / 'manifest.json', manifest)
    print(f"{name}: {len(raw)} raw peaks, {len(peaks)} dedup, {manifest['wall_seconds']:.1f} s", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('fields', nargs='+', help='Field IDs defined in configs/fields.yaml')
    p.add_argument('--depth', choices=('base', 'deep'), default='base')
    p.add_argument('--tag', default='')
    args = p.parse_args()
    root, data_root, cfg = settings()
    if cfg['region'] != 'south':
        p.error('Only south DECam gr is available in this release')
    if args.depth == 'deep':
        for band in 'gr':
            cfg[f'{band}_max'] += .5
    fields = {s['id']: s for s in yaml.safe_load(config_path('fields.yaml').read_text())['fields']}
    model = load_isochrone(data_root / 'resources' / cfg['isochrone'])
    bricks = load_bricks(root)
    for name in args.fields:
        execute(fields[name], root, data_root, cfg, bricks, model, args.depth, args.tag)


if __name__ == '__main__':
    main()
