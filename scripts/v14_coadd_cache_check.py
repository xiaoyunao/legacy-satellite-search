"""Compare packed scratch masks with direct FITS reads on real DR11 bricks."""
import os
from pathlib import Path
from time import monotonic

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import _sample_brick, load_bricks
from ls_satsearch.expansion import unit
from ls_satsearch.run import write_csv, write_json


def run():
    root = Path(os.environ['LS_DR11_ROOT'])
    cache = os.environ['LS_SAT_COADD_CACHE']
    results = []
    sites = {'south': ((31.,-22.),(210.1,14.6),(239.,11.),(45.,-45.)),
             'north': ((214.14,33.1),(132.5,44.),(238.55,64.),(192.,42.))}
    for region, points in sites.items():
        b = load_bricks(root,region)
        b = b[(b['PSFDEPTH_G']>0)&(b['PSFDEPTH_R']>0)]
        tree = cKDTree(unit(b['RA'],b['DEC']))
        _, selected = tree.query(unit(*np.asarray(points).T))
        for row in b[selected]:
            name = row['BRICKNAME'].strip()
            ra = np.linspace(row['RA1'], row['RA1']+(row['RA2']-row['RA1'])%360,151)%360
            dec = np.linspace(row['DEC1'],row['DEC2'],161)
            test = root,name,np.arange(len(ra)),np.arange(len(dec)),ra,dec,sum(1<<i for i in (1,5,6,10,19)),region
            before = monotonic()
            os.environ.pop('LS_SAT_COADD_CACHE', None)
            expected = _sample_brick(test)[-1]
            direct = monotonic()-before
            if expected is None:
                raise ValueError(f'{name} lacks the expected real gr products')
            os.environ['LS_SAT_COADD_CACHE']=cache
            before = monotonic()
            entry = _sample_brick(test)[-1]
            cold = monotonic()-before
            before = monotonic()
            warm_entry = _sample_brick(test)[-1]
            warm = monotonic()-before
            if not (np.array_equal(expected,entry) and np.array_equal(expected,warm_entry)):
                raise ValueError(f'Packed mask changed real exposure sampling for {region}/{name}')
            results.append(dict(region=region,brick=name,tested=len(ra)*len(dec),
                                valid=int(expected.sum()),direct_seconds=direct,
                                first_cache_seconds=cold,warm_cache_seconds=warm))
    out=Path('results/v14/footprint')
    write_csv(out/'coadd_cache_validation.csv',results)
    write_json(out/'coadd_cache_validation.json',dict(job=os.getenv('SLURM_JOB_ID'),matched=len(results)))


if __name__=='__main__':
    run()
