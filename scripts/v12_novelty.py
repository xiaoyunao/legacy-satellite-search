"""Audit round 12 priority groups against public candidate and object catalogues."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from astropy.coordinates import SkyCoord
import yaml

import novelty_audit as archive
from ls_satsearch.run import read_csv, write_csv


download = archive.fetch
static_download = lru_cache(maxsize=8)(download)


def fetch(url):
    return static_download(url) if url.startswith((archive.ASU,archive.UCC)) else download(url)



def probe(row, work, published):
    group=row['group_id']
    out=work/group
    out.mkdir(exist_ok=True,parents=True)
    spec=out/'center.yaml'
    ra,dec=float(row['ra_deg']),float(row['dec_deg'])
    spec.write_text(yaml.safe_dump(dict(ra_deg=ra,dec_deg=dec)))
    result=[]
    try:
        archive.run(out,plan=spec)
        result.extend(dict(r,group_id=group,status='complete')
                      for r in read_csv(out/'novelty_catalog_checks.csv'))
        for r in read_csv(out/'novelty_simbad_types.csv'):
            if int(r['total_5arcmin']):
                result.append(dict(group_id=group,dataset='SIMBAD object type',status='complete',**r))
    except (ValueError,IndexError,KeyError,OSError) as err:
        result.append(dict(group_id=group,dataset='live catalog set',status=type(err).__name__,
                           reason=str(err)))
    target=SkyCoord(ra,dec,unit='deg')
    for item in published:
        pos=SkyCoord(float(item['ra_deg']),float(item['dec_deg']),unit='deg')
        sep=target.separation(pos).arcmin
        result.append(dict(group_id=group,dataset='published coordinate',status='complete',
                           nearest_name=item['object'],nearest_arcmin=sep,
                           source=item['source'],version=item['coordinate_definition']))
    return result


def run(output,work):
    cases=[]
    for f in sorted(Path('results/v12/discovery').glob('*/*/main/priority_modes.csv')):
        cases.extend(r for r in read_csv(f) if r['representative']=='True')
    public=read_csv(Path('results/summary/novelty_published_candidates.csv'))
    public+=read_csv(Path('configs/v12/recent_public_sources.csv'))
    if not cases:
        raise ValueError('No completed priority lists')
    archive.fetch=fetch
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=[row for result in pool.map(lambda r:probe(r,work,public),cases) for row in result]
    output.parent.mkdir(exist_ok=True,parents=True)
    write_csv(output,rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('work',type=Path)
    a=p.parse_args()
    run(a.output,a.work)
