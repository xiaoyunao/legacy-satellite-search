"""Read the completed discovery rasters used to assign residual-search pixels."""
import hashlib
import json
from pathlib import Path

import numpy as np

from .data import Field, ownership, regional_primary, sample_pixels
from .expansion import field_bounds, unit
from .run import sha


def inventory(workspace, data, *, exclude_version=None):
    previous = ('first_batch', 'wide_gaps', 'wide_rollout', '../verification-v6',
                '../discovery-v5', '../holdout-v4', '../group-v3', '../branch-v2')
    folders = [*sorted(workspace.glob('regional_*')), *(workspace / x for x in previous)]
    keys = ('geometry', 'mask', 'subdivision', 'census', 'root')
    records = []
    unique = set()
    for folder in folders:
        if exclude_version and folder.name.startswith(f'regional_{exclude_version}_'):
            continue
        pattern = 'results/summary/*/manifest.json' if folder.name.startswith('regional_') else '**/results/summary/*/manifest.json'
        for path in sorted(folder.glob(pattern)):
            if any(p.startswith(('matched_', 'table8_')) for p in path.parts):
                continue
            m = json.loads(path.read_text())
            f = m.get('field', {})
            if (m.get('status') != 'complete' or m.get('depth') != 'base'
                    or f.get('role') not in ('pilot_dev', 'pilot_eval', 'deep_control')):
                continue
            o = m.get('inputs', {})
            if not all(k in o for k in keys):
                continue
            key = {k: o[k] for k in (*keys, 'region', 'regional_primary') if k in o}
            name = f"{f['id']}-{hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]}"
            raster = m.get('owned_coverage_path', f'cache/{name}/coverage.npy')
            cache = data / raster
            region = m['config'].get('region', 'south')
            identity = (tuple(o['geometry']), region, o['census'],
                        tuple(o['mask']), o['subdivision'], json.dumps(f.get('ownership'), sort_keys=True))
            if identity in unique or not cache.is_file():
                continue
            unique.add(identity)
            records.append(dict(field=f['id'], region=region, survey=o['census'],
                                geometry=o['geometry'], bounds=field_bounds(Field(*o['geometry'])),
                                previous=None if 'owned_coverage_path' in m else f.get('ownership'),
                                cache=name,
                                **({'raster': raster} if 'owned_coverage_path' in m else {}),
                                manifest_sha256=sha(path), manifest=str(path.relative_to(workspace.parent))
                                if path.is_relative_to(workspace.parent) else str(path),
                                effective_deg2=m['area_deg2']))
    return records


def find_local(records, left, right, lo, hi, region):
    center = (left + right) / 2
    half = (right - left) / 2
    return [i for i, record in enumerate(records)
            if record['region'] == region
            and record['bounds'][2] < hi and record['bounds'][3] > lo
            and abs((record['bounds'][0] - center + 180) % 360 - 180) < half + record['bounds'][1]]


def covered(data, records, ra, dec, accepted=None):
    """Sample the raster union. The caller supplies the native-region subset."""
    result = np.zeros(len(ra), dtype=bool)
    for record in records:
        center, half, lo, hi = record['bounds']
        use = (~result & (dec > lo) & (dec < hi)
               & (abs((ra - center + 180) % 360 - 180) < half))
        if accepted is not None and record['survey'] is not None:
            use &= accepted[record['survey']]
        ii = np.flatnonzero(use)
        if record['previous']:
            ii = ii[ownership(ra[ii], dec[ii], record['previous'])]
        if not len(ii):
            continue
        field = Field(*record['geometry'])
        x, y = field.xy(ra[ii], dec[ii])
        path = record.get('raster', f"cache/{record['cache']}/coverage.npy")
        raster = np.load(data / path, mmap_mode='r', allow_pickle=False)
        result[ii] = raster[sample_pixels(field, raster, x, y)]
    return result


def residual_ownership(ra, dec, spec, data, region, bricks, field, census=None,
                       opposite_bricks=None):
    from scipy.spatial import cKDTree
    from astropy.coordinates import SkyCoord

    plan = spec['ownership']
    keep = ownership(ra, dec, plan)
    primary = regional_primary(ra, dec, region)
    if opposite_bricks is None:
        keep &= primary
    else:
        from .regional_pilot import brick_covered
        keep &= ~primary
        ii = np.flatnonzero(keep)
        gr = (opposite_bricks['PSFDEPTH_G'] > 0) & (opposite_bricks['PSFDEPTH_R'] > 0)
        tree = cKDTree(unit(opposite_bricks['RA'], opposite_bricks['DEC']))
        keep[ii] &= ~brick_covered(ra[ii], dec[ii], tree, opposite_bricks, gr)
        return keep

    ii = np.flatnonzero(keep)
    if not len(ii):
        return keep
    a, d = ra[ii], dec[ii]
    local = field.overlap(bricks['RA1'], bricks['RA2'], bricks['DEC1'], bricks['DEC2'])
    local &= (bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
    local_bricks = bricks[local]
    if not len(local_bricks):
        keep[ii] = False
        return keep
    _, near = cKDTree(unit(local_bricks['RA'], local_bricks['DEC'])).query(unit(a, d))
    b = abs(SkyCoord(a, d, unit='deg').galactic.b.deg)
    metadata = local_bricks[near]
    clean = ((b >= plan['abs_b']) & (metadata['EBV'] < plan['ebv'])
             & np.isfinite(metadata['PSFSIZE_G'] + metadata['PSFSIZE_R']))
    choose = clean if plan['quality'] == 'primary' else ~clean
    keep[ii[~choose]] = False
    old = plan.get('history_ids', [])
    if not old or not choose.any():
        return keep
    history = data / 'runs' / plan['history_version'] / 'coverage_history.json'
    index = json.loads(history.read_text())
    if index['inventory_id'] != plan['history_id']:
        raise ValueError('Residual registration points to a different historical raster inventory')
    records = [index['rasters'][j] for j in old]
    jj = ii[choose]
    accepted = None
    if region == 'south' and any(r['survey'] is not None for r in records):
        accepted = {k: census.accept(ra[jj], dec[jj], k) for k in (0, 1, 2, 3)}
    keep[jj] &= ~covered(data, records, ra[jj], dec[jj], accepted)
    return keep
