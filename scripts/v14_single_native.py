"""Register singly imaged regions outside the nominal North/South split."""
import os
from pathlib import Path

import numpy as np
import yaml

from ls_satsearch.run import sha, write_json


def run():
    data = Path(os.environ['LS_SAT_DATA'])/'runs/v14'
    edges = np.linspace(-90,90,73)
    cohort = 'north_single_native'
    with np.load(data/'north_outside_primary.npz',allow_pickle=False) as f:
        ra,dec = f['ra'],f['dec']
    rows=[]
    for j,(lo,hi) in enumerate(zip(edges[:-1],edges[1:])):
        band = (dec>=lo)&(dec<hi)
        if not band.any():
            continue
        mid = (lo+hi)/2
        columns = int(np.ceil(360*np.cos(np.deg2rad(mid))/2.5))
        dx=360/columns
        bucket=np.floor(ra[band]/dx).astype(int)
        for col in np.unique(bucket):
            tile=dict(ra_lo=float(col*dx),ra_hi=float((col+1)*dx),dec_lo=float(lo),dec_hi=float(hi))
            rows.append(dict(id=f'v14_{cohort}_{len(rows)+1:03d}',ra=float((col+.5)*dx),dec=float(mid),
                             width=2.55,role='pilot_dev' if (j+col)%4==0 else 'pilot_eval',
                             layer=cohort,region='north',native_primary=False,
                             proxy_area_deg2=float((bucket==col).sum()*360**2/np.pi/(12*512**2)),
                             ownership=dict(partition=tile,quality='extension',single_native=True)))
    out=Path('configs/v14/cohorts')/cohort
    out.mkdir(exist_ok=True,parents=True)
    path=out/'fields.yaml'
    path.write_text(yaml.safe_dump(dict(fields=rows),sort_keys=False))
    (out/'search.yaml').write_bytes(Path('configs/v12/cohorts/north/search.yaml').read_bytes())
    write_json(out/'registration.json',dict(fields_sha256=sha(path),count=len(rows),
               audit_positions_sha256=sha(data/'north_outside_primary.npz'),
               total_proxy_deg2=sum(r['proxy_area_deg2'] for r in rows),
               job=os.getenv('SLURM_JOB_ID')))


if __name__ == '__main__':
    run()
