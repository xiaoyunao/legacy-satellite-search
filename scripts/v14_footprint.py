"""Register disjoint DR11 residual fields against previously measured search rasters."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.coverage_history import covered, find_local, inventory
from ls_satsearch.data import load_bricks, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.fields import Census
from ls_satsearch.regional_pilot import brick_covered
from ls_satsearch.run import sha, write_csv, write_json


def register(plan, output, report):
    spec = yaml.safe_load(plan.read_text())
    root = Path(os.environ['LS_DR11_ROOT'])
    data = Path(os.environ['LS_SAT_DATA'])
    workspace = Path.cwd()
    version = spec['version']
    records = inventory(workspace, data, exclude_version=version)
    if not records:
        raise ValueError('No historical observed rasters available')
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    archive = data / 'runs' / version
    archive.mkdir(parents=True, exist_ok=True)
    index = archive / 'coverage_history.json'
    if index.exists() and json.loads(index.read_text())['inventory_id'] != digest:
        raise ValueError('Prior registration has a different frozen inventory; use a new version')
    write_json(index, dict(inventory_id=digest, rasters=records))

    grid = HEALPix(nside=spec['nside'], order='ring')
    lon, lat = grid.healpix_to_lonlat(np.arange(grid.npix))
    all_ra, all_dec = lon.deg, lat.deg
    pixel = float(grid.pixel_area.to_value(u.deg**2))
    atlas = Census(data)
    step = spec['width_deg']
    edges = np.linspace(-90, 90, round(180 / step) + 1)
    names = ('primary', 'extension')
    fields = {(layer, quality): [] for layer in spec['layers'] for quality in names}
    audit = {(layer, quality): [] for layer, quality in fields}
    overlaps = {}
    for region in ('north', 'south'):
        query = regional_primary(all_ra, all_dec, region)
        ra, dec = all_ra[query], all_dec[query]
        bricks = load_bricks(root, region)
        gr = (bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
        tree = cKDTree(unit(bricks['RA'], bricks['DEC']))
        use = brick_covered(ra, dec, tree, bricks, gr)
        ra, dec = ra[use], dec[use]
        band_bricks = bricks[gr]
        tree = cKDTree(unit(band_bricks['RA'], band_bricks['DEC']))
        _, nearest = tree.query(unit(ra, dec))
        row = band_bricks[nearest]
        b = abs(SkyCoord(ra, dec, unit='deg').galactic.b.deg)
        clean = ((b >= spec['min_abs_b']) & (row['EBV'] < spec['max_ebv'])
                 & np.isfinite(row['PSFSIZE_G'] + row['PSFSIZE_R']))
        census = {k: atlas.accept(ra, dec, k) for k in range(4)} if region == 'south' else None
        if census is not None and not np.all(sum(v.astype(np.int8) for v in census.values()) == 1):
            raise ValueError('Census layers must cover each coordinate exactly once')

        # Save a coarse sky layer alongside the higher-resolution owned search grids.
        prefix = dict(ra=ra, dec=dec, clean=clean, ebv=row['EBV'], g_seeing=row['PSFSIZE_G'],
                      r_seeing=row['PSFSIZE_R'], g_depth=row['PSFDEPTH_G'], r_depth=row['PSFDEPTH_R'])
        observed = np.zeros(len(ra), bool)
        for lo, hi in zip(edges[:-1], edges[1:]):
            ring = np.flatnonzero((dec >= lo) & (dec < hi))
            if not len(ring):
                continue
            d0 = np.rad2deg(np.arcsin((np.sin(np.deg2rad(lo)) + np.sin(np.deg2rad(hi))) / 2))
            cos = np.cos(np.deg2rad(d0))
            columns = max(1, int(np.ceil(360 * cos / step)))
            width = max(2 * 180 / np.pi * (np.sin(np.deg2rad(hi)) - np.sin(np.deg2rad(d0))) / cos,
                        360 / columns * cos) + .02
            bucket = np.minimum((ra[ring] / (360 / columns)).astype(int), columns - 1)
            for col in np.unique(bucket):
                jj = ring[bucket == col]
                left, right = np.array([col, col + 1]) * 360 / columns
                local = find_local(records, left, right, lo, hi, region)
                previous = covered(data, [records[i] for i in local], ra[jj], dec[jj],
                                   {k: census[k][jj] for k in census} if census is not None else None)
                observed[jj] = previous
                partition = dict(ra_lo=float(left), ra_hi=float(right),
                                 dec_lo=float(lo), dec_hi=float(hi))
                for layer, rule in spec['layers'].items():
                    if rule['region'] != region:
                        continue
                    survey = rule.get('census')
                    match = census[survey][jj] if survey is not None else np.ones(len(jj), bool)
                    for quality, sample in zip(names, (clean[jj], ~clean[jj])):
                        select = match & sample
                        count, visited = int(select.sum()), int((select & previous).sum())
                        if not count:
                            continue
                        pending = (count - visited) * pixel
                        audit[layer, quality].append(dict(**partition, brick_proxy_deg2=count * pixel,
                                                           prior_raster_proxy_deg2=visited * pixel,
                                                           residual_proxy_deg2=pending))
                        if pending <= 0:
                            continue
                        cohort = layer if quality == 'primary' else layer + '_extension'
                        block = fields[layer, quality]
                        # Hold out one in five extension tiles, using only the sky partition index.
                        dev = quality == 'extension' and (round((lo + 90) * 10) + col + spec['seed']) % 5 == 0
                        block.append(dict(id=f'{version}_{cohort}_{len(block)+1:04d}',
                                          ra=float((left + right) / 2), dec=float(d0), width=float(width),
                                          role='pilot_dev' if dev else 'pilot_eval',
                                          layer=layer, region=region, survey=survey,
                                          proxy_area_deg2=pending,
                                          ownership=dict(partition=partition, quality=quality, abs_b=spec['min_abs_b'],
                                                         ebv=spec['max_ebv'], history_version=version,
                                                         history_id=digest, history_ids=local)))
        if census is not None:
            prefix['census'] = sum(k * v.astype(np.uint8) for k, v in census.items())
        np.savez_compressed(archive / f'{region}_brick_grid.npz', **prefix, observed=observed)
        # Native overlap uses the original independent footprints before the ownership cut.
        coords = np.flatnonzero((all_dec >= 20) & (all_dec < 60))
        native_raw = brick_covered(all_ra[coords], all_dec[coords],
                                   cKDTree(unit(bricks['RA'], bricks['DEC'])), bricks, gr)
        overlaps[region] = coords[native_raw]
    dual = np.intersect1d(overlaps['north'], overlaps['south'])
    write_csv(report / 'native_overlap_proxy.csv',
              [dict(proxy_deg2=len(dual) * pixel, dec_min_deg=20, dec_max_deg=60, nside=grid.nside)])
    np.savez_compressed(archive / 'overlap_grid.npz', ra=all_ra[dual], dec=all_dec[dual])

    summary = []
    for (layer, quality), block in fields.items():
        cohort = layer if quality == 'primary' else layer + '_extension'
        folder = output / 'cohorts' / cohort
        folder.mkdir(exist_ok=True, parents=True)
        path = folder / 'fields.yaml'
        with path.open('w') as stream:
            yaml.safe_dump(dict(seed=spec['seed'], plan_sha256=sha(plan), prior_raster_inventory=digest,
                                fields=block), stream, sort_keys=False)
        region = spec['layers'][layer]['region']
        search = Path('configs/v12/cohorts/north/search.yaml' if region == 'north' else 'configs/v7/search.yaml')
        (folder / 'search.yaml').write_bytes(search.read_bytes())
        rows = audit[layer, quality]
        summary.append(dict(cohort=cohort, region=region, quality=quality, registered=len(block),
                            development=sum(f['role'] == 'pilot_dev' for f in block),
                            brick_proxy_deg2=sum(r['brick_proxy_deg2'] for r in rows),
                            prior_raster_proxy_deg2=sum(r['prior_raster_proxy_deg2'] for r in rows),
                            residual_proxy_deg2=sum(r['residual_proxy_deg2'] for r in rows),
                            fields_sha256=sha(path)))
        print(cohort, len(block), sum(f['proxy_area_deg2'] for f in block), flush=True)
    write_csv(report / 'registration_area.csv', summary)
    write_json(report / 'registration.json',
               dict(job=os.getenv('SLURM_JOB_ID'), nside=grid.nside, archive_inventory=digest,
                    prior_measured_rasters=len(records), plan_sha256=sha(plan)))
    write_csv(report / 'historical_rasters.csv',
              [{k: r[k] for k in ('field', 'region', 'survey', 'effective_deg2', 'manifest_sha256')}
               for r in records])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('report', type=Path)
    args = p.parse_args()
    args.report.mkdir(parents=True, exist_ok=True)
    register(**vars(args))
