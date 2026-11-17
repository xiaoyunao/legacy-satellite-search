"""Register remaining South PS1 cores using metadata and previous geometry."""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import yaml
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
from scipy.spatial import cKDTree

from ls_satsearch.data import Field, load_bricks, regional_primary
from ls_satsearch.expansion import core_disjoint, field_bounds, unit
from ls_satsearch.fields import Census
from ls_satsearch.regional_pilot import brick_covered, previous_cores
from ls_satsearch.run import settings, sha, write_json


def run(plan, output):
    root, data, _ = settings()
    spec = yaml.safe_load(plan.read_text())
    rule = spec['south_ps1']
    history = sorted(Path('configs').glob('v1[12]/cohorts/*/fields.yaml'))
    # The smaller Round 12 cores were registered separately.
    history.append(Path('configs/v12g/cohorts/south_ps1/fields.yaml'))
    bounds, hashes = previous_cores(history)
    old = np.asarray(bounds)
    occupied = np.empty((len(old) + rule['count'], 4))
    occupied[:len(old)] = old
    atlas = Census(data)
    bricks = load_bricks(root, 'south')
    tree = cKDTree(unit(bricks['RA'], bricks['DEC']))
    good = ((bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
            & (bricks['EBV'] < spec['max_ebv'])
            & np.isfinite(bricks['PSFSIZE_G'] + bricks['PSFSIZE_R']))
    rng = np.random.default_rng(spec['seed'])
    fields, passes = [], []
    for grid in rule['passes']:
        width, minimum = grid['width'], grid['minimum']
        hp = HEALPix(nside=grid['nside'], order='ring')
        lon, lat = hp.healpix_to_lonlat(np.arange(hp.npix))
        ra, dec = lon.deg, lat.deg
        center = regional_primary(ra, dec, 'south') & (abs(dec) < 74) & atlas.accept(ra, dec, 3)
        use = np.flatnonzero(center)
        center[use] &= brick_covered(ra[use], dec[use], tree, bricks, good)
        use = np.flatnonzero(center)
        center[use] &= abs(SkyCoord(ra[use], dec[use], unit='deg').galactic.b.deg) >= spec['min_abs_b']
        xy = np.meshgrid(*(np.linspace(-width*30, width*30, 17),)*2)
        begin = len(fields)
        for i in rng.permutation(np.flatnonzero(center)):
            field = Field(float(ra[i]), float(dec[i]), width, 1/6, buffer=0)
            geom = field_bounds(field)
            if not core_disjoint(geom, occupied[:len(old)+len(fields)]):
                continue
            a, d = field.sky(*xy)
            a, d = a.ravel(), d.ravel()
            if not regional_primary(a, d, 'south').all():
                continue
            assigned = atlas.accept(a, d, 3)
            if assigned.mean() < minimum:
                continue
            valid = assigned & brick_covered(a, d, tree, bricks, good)
            valid &= abs(SkyCoord(a, d, unit='deg').galactic.b.deg) >= spec['min_abs_b']
            fraction = float(valid.mean())
            if fraction < minimum:
                continue
            occupied[len(old)+len(fields)] = geom
            fields.append(dict(id=f'v13_south_ps1_{len(fields)+1:04d}', ra=field.ra, dec=field.dec,
                               width=width, role='pilot_eval', layer='south_ps1', region='south',
                               survey=3, proxy_coverage=fraction, proxy_area_deg2=width**2*fraction))
            if len(fields) == rule['count']:
                raise RuntimeError('Registration cap reached before tiling passes finished')
        block = fields[begin:]
        passes.append(dict(grid, cores=len(block), proxy_deg2=sum(f['proxy_area_deg2'] for f in block)))
        print(passes[-1], flush=True)
    output.mkdir(parents=True, exist_ok=True)
    path = output/'fields.yaml'
    path.write_text(yaml.safe_dump(dict(seed=spec['seed'], plan_sha256=sha(plan),
                                       previous_fields_sha256=hashes, fields=fields), sort_keys=False))
    (output/'search.yaml').write_bytes(Path('configs/v7/search.yaml').read_bytes())
    policy = json.loads(Path('configs/v7/production.json').read_text())
    write_json(output/'production.json', dict(policy, field_file_sha256=sha(path)))
    write_json(output/'registration.json', dict(job=os.getenv('SLURM_JOB_ID'), passes=passes,
               plan_sha256=sha(plan), fields_sha256=sha(path)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    run(**vars(parser.parse_args()))
