"""Compare four fixed-centre misses with matched real positions in the same fields."""

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import shapely

from ls_satsearch.data import select
from ls_satsearch.run import field_cache, read_csv, sha, write_csv, write_json
from ls_satsearch.search import CMD, binomial_tail_score, exact_onoff, load_isochrone
from scripts.v14_mask_tiles import cache_key
from scripts.v14_missed_controls import MASK, NAMES, OUT, covering

SEED = 726051
NULL_LIMIT = 400
MAX_DRAW = 16000
AREA_CALIPER = .1
NEIGHBOURHOOD = 90.


def measure(field, area, center, radius, arm):
    tree, cmd = arm
    n_on, n_off, a_on, a_off = exact_onoff(field, *center, radius, tree, area, cmd)
    score = binomial_tail_score(n_on, n_on + n_off, a_on / (a_on + a_off)) if a_on and a_off else 0.
    return score, a_on, a_off


def disk_count(prefix, iy, ix, r_pixels, include_edge=True):
    """Count binary-mask pixel centres in a disk using summed rows."""
    jy, jx = int(iy), int(ix)
    fy, fx = round(iy - jy, 8), round(ix - jx, 8)
    half = math.ceil(r_pixels)
    j = np.arange(max(-half, -jy), min(half + 1, len(prefix) - jy))
    dy = j + .5 - fy
    inside = abs(dy) <= r_pixels if include_edge else abs(dy) < r_pixels
    j, dy = j[inside], dy[inside]
    span = np.sqrt(np.maximum(0., r_pixels**2 - dy**2))
    left, right = fx - span - .5, fx + span - .5
    if include_edge:
        lo, hi = np.ceil(left), np.floor(right) + 1
    else:
        lo, hi = np.floor(left) + 1, np.ceil(right)
    lo = np.clip(lo.astype(int) + jx, 0, prefix.shape[1] - 1)
    hi = np.clip(hi.astype(int) + jx, 0, prefix.shape[1] - 1)
    return int(np.maximum(0, prefix[j + jy, hi] - prefix[j + jy, lo]).sum())


def aperture_areas(prefix, field, step, point, radii):
    ix, iy = (point + field.limit) / step
    rows = []
    for r in radii:
        on = disk_count(prefix, iy, ix, 1.5 * r / step)
        off = disk_count(prefix, iy, ix, 6 * r / step) - disk_count(prefix, iy, ix, 3.5 * r / step, False)
        rows.append((on * step**2, off * step**2))
    return np.array(rows)


def scores(tree, point, radii, areas):
    distance = np.linalg.norm(tree.data[tree.query_ball_point(point, 6 * max(radii))] - point, axis=1)
    values = []
    for radius, (a_on, a_off) in zip(radii, areas):
        n_on = int(np.count_nonzero(distance <= 1.5 * radius))
        n_off = int(np.count_nonzero((distance >= 3.5 * radius) & (distance <= 6 * radius)))
        values.append(binomial_tail_score(n_on, n_on + n_off, a_on / (a_on + a_off)))
    return values


def experiment(truth, truths, record, entry, registration, previous, rng, inputs):
    path = Path(record['manifest'])
    if sha(path) != record['manifest_sha256']:
        raise ValueError('Original scan manifest changed')
    scan = json.loads(path.read_text())
    cfg = scan['config']
    root, data = (Path(os.environ[k]) for k in ('LS_DR11_ROOT', 'LS_SAT_DATA'))
    template = data / 'resources' / cfg['isochrone']
    if sha(template) != scan['model_sha256']:
        raise ValueError('Original model changed')
    inputs.update({str(path): sha(path), str(template): sha(template)})
    field, raw, area, _ = field_cache(root, data, scan['field'], cfg, None)
    locus = load_isochrone(template)[2]
    base_rows = [r for r in previous if r['name'] == truth['name'] and r['field'] == record['field']
                 and r['arm'] == 'baseline' and r['dm_role'] == 'nearest_grid'
                 and r['formal_grid_scale'] == 'True' and r['mask_eligible'] == 'True']
    if not base_rows:
        raise ValueError('No qualifying target scales in the original diagnostic')
    radii = [float(r['rh_arcmin']) for r in base_rows]
    dm, = {float(r['dm']) for r in base_rows}
    center = np.array(field.xy(float(truth['ra_deg']), float(truth['dec_deg'])))
    arms = []
    for c in (cfg, dict(cfg, g_max=cfg['g_max'] + .5, r_max=cfg['r_max'] + .5)):
        stars, *_ = select(raw, field, area, c)
        arms.append((cKDTree(stars[:, :2]), CMD.top_hat(stars[:, 2:4], stars[:, 4:6], dm, locus)))
    reference = np.array([[measure(field, area, center, rh, arm) for rh in radii] for arm in arms])
    if not np.allclose(reference[0, :, 0], [float(r['fixed_centre_score']) for r in base_rows]):
        raise ValueError('Baseline controls do not reproduce the original fixed-centre measurement')
    for rh, original in zip(radii, reference[1, :, 0]):
        row, = [r for r in previous if r['name'] == truth['name'] and r['field'] == record['field']
                and r['arm'] == 'deeper_diagnostic' and r['dm_role'] == 'nearest_grid'
                and float(r['rh_arcmin']) == rh]
        if not np.isclose(original, float(row['fixed_centre_score'])):
            raise ValueError('Deeper controls do not reproduce the original measurement')
    area_min = np.array([(cfg['min_on_fraction'] * math.pi * (1.5 * rh)**2,
                         cfg['min_off_fraction'] * math.pi * (6**2 - 3.5**2) * rh**2)
                        for rh in radii])
    expected_area = reference[0, :, 1:]
    step = field.step / (len(area) // field.n)
    prefix = np.empty((area.shape[0], area.shape[1] + 1), dtype=np.int32)
    prefix[:, 0] = 0
    np.cumsum(area, axis=1, dtype=np.int32, out=prefix[:, 1:])
    if not np.array_equal(aperture_areas(prefix, field, step, center, radii), expected_area):
        raise ValueError('Summed rows differ from the frozen mask count at the target')
    cmd_trees = [cKDTree(tree.data[cmd]) for tree, cmd in arms]
    region_masks = []
    for label, bounds in enumerate(entry['bounds']):
        if bounds is not None:
            p = Path(registration['cache']) / f"{entry['cache_key']}-{label}.wkb"
            if sha(p) != entry['geometry_sha256'][p.name]:
                raise ValueError('Actual mask geometry changed')
            inputs[str(p)] = sha(p)
            region_masks.append(shapely.from_wkb(p.read_bytes()))
    polygon = shapely.union_all(region_masks)
    xy = rng.uniform(-NEIGHBOURHOOD, NEIGHBOURHOOD, size=(MAX_DRAW, 2))
    xy = xy[np.hypot(*xy.T) <= NEIGHBOURHOOD] + center
    ra, dec = field.sky(*xy.T)
    xy = xy[shapely.contains_xy(polygon, ra, np.sin(np.deg2rad(dec)))]
    # Leave known cores out of potential on apertures. The outer annuli can overlap
    # each other and the target environment, so these are descriptive controls.
    for known in truths:
        known_xy = field.xy(float(known['ra_deg']), float(known['dec_deg']))
        avoid = 1.5 * max(radii) + max(3., 4 * float(known['theta_h_arcmin']))
        xy = xy[np.hypot(*(xy - known_xy).T) > avoid]
    null = []
    for point in xy:
        use_area = aperture_areas(prefix, field, step, point, radii)
        if (np.any(use_area < area_min) or
                np.any(abs(use_area / expected_area - 1) > AREA_CALIPER)):
            continue
        baseline, deep = (scores(tree, point, radii, use_area) for tree in cmd_trees)
        if not null:
            original = np.array([measure(field, area, point, rh, arms[0]) for rh in radii])
            if not (np.array_equal(use_area, original[:, 1:]) and np.allclose(baseline, original[:, 0])):
                raise ValueError('Fast control count differs from the original procedure')
        null.append((max(baseline), max(deep)))
        if len(null) == NULL_LIMIT:
            break
    if not null:
        raise ValueError('No area-compatible fixed control centres in the local mask')
    null = np.array(null)
    target = reference[:, :, 0].max(axis=1)
    values = np.column_stack((null, null[:, 1] - null[:, 0]))
    summary = []
    for label, measurements, value in zip(('baseline', 'deeper', 'paired_delta'),
                                           values.T, (*target, target[1] - target[0])):
        n_greater = int((measurements >= value).sum())
        q50, q90, q95, q99 = np.quantile(measurements, [.5, .9, .95, .99])
        summary.append(dict(target=truth['name'], field=record['field'], endpoint=label, dm=dm,
                            tested_radii_arcmin='|'.join(f'{r:g}' for r in radii),
                            target_value=value, n_same_field_centres=len(null),
                            n_at_least_target=n_greater, descriptive_fraction=n_greater / len(null),
                            null_median=q50, null_p90=q90, null_p95=q95, null_p99=q99,
                            overlapping_control_apertures=True, blind_search=False))
    return summary


def main(output):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated compute CPUs')
    receipt = MASK / 'post_outside_C_registration_20261120.json'
    rec = json.loads(receipt.read_text())
    path = Path(rec['registration'])
    if sha(path) != rec['registration_sha256']:
        raise ValueError('Original mask registration changed')
    reg = json.loads(path.read_text())
    index = Path(reg['output']) / 'vector_index.json'
    check = json.loads((index.parent / 'overlay_repair_registration.json').read_text())
    if check['vector_index_sha256'] != sha(index):
        raise ValueError('Original WCS geometry index changed')
    rows = {r['cache_key']: r for r in json.loads(index.read_text())['records']}
    fields = {cache_key(r, reg): r for r in reg['records']}
    benchmarks = Path('references/benchmarks.csv')
    known_audit = OUT / 'known_recovery_summary.csv'
    fixed = OUT / 'missed_controls_fixed_diagnostics.csv'
    previous = read_csv(fixed)
    truth = [r for r in read_csv(benchmarks) if r['name'] in NAMES]
    known = [r for r in read_csv(known_audit) if r['theta_h_arcmin']]
    inputs = {str(p): sha(p) for p in (receipt, path, index, benchmarks, known_audit, fixed)}
    rng = np.random.default_rng(SEED)
    results = []
    for r in sorted(truth, key=lambda r: r['name']):
        for key in covering(reg, rows.values(), float(r['ra_deg']), float(r['dec_deg'])):
            results.extend(experiment(r, known, fields[key], rows[key], reg, previous, rng, inputs))
        print(dict(target=r['name'], accumulated_rows=len(results)), flush=True)
    output.mkdir(parents=True, exist_ok=False)
    table = output / 'fixed_position_control_ranks.csv'
    write_csv(table, results)
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], seed=SEED, inputs=inputs,
        rows=len(results), table_sha256=sha(table), code_sha256=sha(Path(__file__)),
        area_relative_caliper=AREA_CALIPER, within_arcmin=NEIGHBOURHOOD, max_controls=NULL_LIMIT,
        scope='Paired catalogue limits at the same fixed distance and eligible scale set. Random real positions within the same qualified mask exclude known cores and match usable on/off areas. Apertures overlap, so ranks are descriptive. No independent tail uncertainty, survey-wide trials correction, blind recall or classification.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    main(p.parse_args().output)
