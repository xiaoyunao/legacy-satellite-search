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


def publish_peak_cache(summary, work, peaks):
    """Keep the full R14 intermediate table on scratch at its existing logical path."""
    target=work/'deduplicated_peaks.csv'
    write_csv(target,peaks)
    logical=summary/'deduplicated_peaks.csv'
    temporary=logical.with_suffix('.csv.link.tmp')
    temporary.symlink_to(target.resolve())
    temporary.replace(logical)
    return target


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


def runs_path(data_root):
    return data_root / 'runs' / os.environ.get('LS_SAT_RUN_VERSION', 'v2')


def recovery(rows, truth, field, coverage, cfg, depth):
    from .hypotheses import truth_branch

    records = []
    branch = truth_branch(float(truth['D_kpc']))
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
    for method in cfg.get('methods', ('A', 'B')):
        record = dict(name=truth['name'], branch=branch, method=method, depth=depth, covered=covered,
                      core_valid_fraction=fraction, off_valid_fraction=off_fraction,
                      entered_peak_table=False, truth_dm=5 * np.log10(float(truth['D_kpc'])) + 10,
                      scale_below_grid=float(truth['theta_h_arcmin']) < min(cfg['radii_arcmin']))
        if covered:
            pos = SkyCoord(float(truth['ra_deg']), float(truth['dec_deg']), unit='deg')
            peers = [r for r in rows if r['method'] == method and r['branch'] == branch]
            if peers:
                coords = SkyCoord([r['ra_deg'] for r in peers], [r['dec_deg'] for r in peers], unit='deg')
                sep = pos.separation(coords).arcmin
                nearby = np.flatnonzero(sep <= max(cfg['match_min_arcmin'], cfg['match_rh_factor'] * radius))
                if len(nearby):
                    top = peers[nearby[0]]
                    record.update(spatial_score=top['score'], spatial_rank=top['rank'],
                                  spatial_dm=top['dm'], spatial_offset_arcmin=sep[nearby[0]])
                indices = np.flatnonzero((sep <= max(cfg['match_min_arcmin'], cfg['match_rh_factor'] * radius)) &
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

    field = Field(spec['ra'], spec['dec'], spec['width'], min(cfg['radii_arcmin']) / 3,
                  buffer=spec.get('buffer_arcmin',102))
    region = cfg.get('region', 'south')
    primary = spec.get('native_primary', cfg.get('regional_primary', region == 'north'))
    key = dict(geometry=[field.ra, field.dec, field.width, field.step, field.buffer],
               mask=cfg['reject_maskbits'], subdivision=cfg['coverage_subdivision'],
               census=spec.get('survey'), root=str(root))
    if region != 'south' or primary:
        key.update(region=region, regional_primary=primary)
    cache = data_root / 'cache' / f"{spec['id']}-{hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]}"
    cache.mkdir(exist_ok=True, parents=True)
    xs = cache / 'catalog.npy'
    ar = cache / 'coverage.npy'
    info_path = cache / 'inputs.json'
    with (cache / 'prepare.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if info_path.exists() and xs.exists() and ar.exists():
            return field, np.load(xs, allow_pickle=False), np.load(ar, allow_pickle=False), json.loads(info_path.read_text())
        sources, provenance = sweeps(root, field, region)
        if primary:
            from .data import regional_primary
            sources = sources[regional_primary(sources['RA'], sources['DEC'], region)]
        if bricks is None:
            bricks = load_bricks(root, region)
        survey = spec.get('survey')
        coverage, mask_info = make_area(root, field, bricks, sum(1 << bit for bit in cfg['reject_maskbits']),
                                       cfg['coverage_subdivision'],
                                       Census(data_root) if survey is not None else None, survey,
                                       region=region, primary=primary)
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
    work = runs_path(data_root) / name
    for path in (summary, figures, work):
        path.mkdir(exist_ok=True, parents=True)
    sample, cutflow, valid, mags, chosen = select(sources, field, area, cfg)
    owned = spec.get('ownership')
    area_for_count = area
    region = cfg.get('region', 'south')
    if owned:
        from .data import ownership, regional_primary

        if 'quality' in owned:
            from .coverage_history import residual_ownership
            from .fields import Census

            census = Census(data_root) if region == 'south' else None
            opposite = None
            if owned.get('single_native'):
                opposite = load_bricks(root,'south' if region=='north' else 'north')
                close = field.overlap(opposite['RA1'],opposite['RA2'],opposite['DEC1'],opposite['DEC2'])
                # Nearest-brick coverage needs enough neighbours near thin footprint edges.
                if close.sum() >= 4:
                    opposite = opposite[close]

            def own(ra, dec):
                return residual_ownership(ra, dec, spec, data_root, region, bricks, field, census,
                                          opposite_bricks=opposite)
        else:
            def own(ra, dec):
                return ownership(ra, dec, owned) & regional_primary(ra, dec, region)

    if owned:
        area_for_count = area.copy()
        cell = field.step / cfg['coverage_subdivision']
        axis = (np.arange(len(area)) + .5)*cell - field.limit
        rows = np.flatnonzero(abs(axis) < field.width*30)
        core = area_for_count[np.ix_(rows,rows)]
        iy,ix = np.nonzero(core)
        ra,dec = field.sky(axis[rows[ix]],axis[rows[iy]])
        keep = own(ra, dec)
        core[iy,ix] &= keep
        area_for_count[np.ix_(rows,rows)] = core
    effective_area, frac = coverage_metrics(field, area_for_count, cfg)
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
    region = cfg.get('region','south')
    manifest = dict(field=spec, bandpass='BASS g,r' if region == 'north' else 'DECam g,r',
                    release=f'DR11 {region}',
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
    if owned and 'quality' in owned:
        raster_path = work / 'owned_coverage.npy'
        stage = raster_path.with_suffix('.tmp.npy')
        np.save(stage, area_for_count, allow_pickle=False)
        stage.replace(raster_path)
        manifest['owned_coverage_path'] = str(raster_path.relative_to(data_root))
        manifest['background_core_deg2'] = coverage_metrics(field, area, cfg)[0]
    write_json(summary / 'manifest.json', manifest)
    from .plots import overview

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
    if owned and raw:
        from .search import deduplicate
        ra = np.array([p['ra_deg'] for p in raw])
        dec = np.array([p['dec_deg'] for p in raw])
        keep = own(ra, dec)
        raw = [p for p,use in zip(raw,keep) if use]
        peaks = deduplicate(raw,cfg.get('main_dm_max',20.75))
    write_csv(work / 'all_template_peaks.csv', raw)
    if os.getenv('LS_SAT_RUN_VERSION')=='v14':
        peak_cache=publish_peak_cache(summary,work,peaks)
        manifest['deduplicated_peaks_path']=str(peak_cache.relative_to(data_root))
    else:
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
    if not os.environ.get('LS_SAT_V2_WORKSPACE'):
        p.error('Use an isolated v2 workspace and set LS_SAT_V2_WORKSPACE=1')
    root, data_root, cfg = settings()
    if cfg['region'] not in ('south', 'north'):
        p.error('Choose an explicit north or south region')
    if args.depth == 'deep':
        for band in 'gr':
            cfg[f'{band}_max'] += .5
    fields = {s['id']: s for s in yaml.safe_load(config_path('fields.yaml').read_text())['fields']}
    model = load_isochrone(data_root / 'resources' / cfg['isochrone'])
    bricks = load_bricks(root, cfg['region'])
    for name in args.fields:
        spec = fields[name]
        field_cfg = dict(cfg, methods=cfg.get('method_fields', {}).get(name, cfg.get('methods', ['A','B'])))
        execute(spec, root, data_root, field_cfg, bricks, model, args.depth, args.tag)


if __name__ == '__main__':
    main()
