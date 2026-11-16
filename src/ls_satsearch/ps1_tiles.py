"""Acquire bounded, paginated PS1 stack input in NERSC scratch."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import io
from itertools import product
import math
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import yaml

from .data import Field
from .ps1_probe import URL
from .run import config_path, settings, sha, write_json

COLUMNS = ('objID','raStack','decStack','primaryDetection','gPSFMag','rPSFMag',
           'gPSFMagErr','rPSFMagErr','iPSFMag','iKronMag','iPSFMagErr')
RADIUS = .49
PAGE_SIZE = 25000


def design(spec, matched):
    field = Field(spec['ra'], spec['dec'], matched['width_deg'],
                  min(matched['radii_arcmin']) / 3, buffer=matched['buffer_arcmin'])
    n = math.ceil(2 * field.limit / 60 / .63)
    centers = (np.arange(n) + .5) * 2 * field.limit / n - field.limit
    return field, [tuple(map(float, field.sky(x, y))) for x,y in product(centers,repeat=2)]


def download(query):
    for attempt in range(4):
        try:
            with urlopen(query,timeout=80) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as e:
            if attempt==3 or isinstance(e,HTTPError) and e.code not in (429,500,502,503,504):
                raise
            time.sleep(2**attempt)


def boundary_repeats(ids, previous, page_size):
    """Accept an equal boundary while rejecting reversed and stalled pages."""
    if (len(ids) > page_size or any(a > b for a,b in zip(ids,ids[1:])) or
            (previous is not None and ids and
             (ids[0] < previous or (len(ids) == page_size and ids[-1] == previous)))):
        raise ValueError('MAST pagination reversed order or stopped advancing')
    return sum(ident == previous for ident in ids)


def acquire(field_id, workers=1):
    _,data,_=settings()
    matched=yaml.safe_load(config_path('matched.yaml').read_text())
    spec=next(f for f in matched['fields'] if f['id']==field_id)
    field,tiles=design(spec,matched)
    out=data/'resources/ps1/tiles-v3'/field_id
    out.mkdir(exist_ok=True,parents=True)
    def acquire_tile(task):
        i,(ra,dec) = task
        result = []
        total=0
        previous=None
        for page in range(1,21):
            query=URL+'.csv?'+urlencode(dict(ra=f'{ra:.8f}',dec=f'{dec:.8f}',radius=RADIUS,
                        primaryDetection=1,columns='['+','.join(COLUMNS)+']',sort_by='objID.asc',
                        pagesize=PAGE_SIZE,page=page))
            path=out/f'cone-{i:02d}-{page:02d}.csv'
            if path.exists():
                contents=path.read_bytes()
            else:
                contents=download(query)
            reader=csv.DictReader(io.StringIO(contents.decode('utf-8-sig')))
            if not reader.fieldnames or not set(COLUMNS)<=set(reader.fieldnames):
                raise ValueError(f'Invalid MAST response for {field_id}, cone {i}, page {page}')
            ids = [int(r['objID']) for r in reader]
            count = len(ids)
            repeats=boundary_repeats(ids,previous,PAGE_SIZE)
            if not path.exists():
                tmp=path.with_suffix('.tmp')
                tmp.write_bytes(contents)
                tmp.replace(path)
            result.append(dict(tile=i,page=page,ra_deg=ra,dec_deg=dec,radius_deg=RADIUS,
                               rows=count,boundary_repeats=repeats,path=path.name,sha256=sha(path),url=query))
            total+=count
            if count<PAGE_SIZE:
                break
            previous=ids[-1]
        else:
            raise RuntimeError(f'Page limit reached for cone {i} in {field_id}')
        print(f'{field_id} {i+1}/{len(tiles)} {total}',flush=True)
        return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pages = [p for tile in executor.map(acquire_tile,enumerate(tiles)) for p in tile]
    write_json(out/'manifest.json',dict(field=spec,limit_arcmin=field.limit,pages=pages,
                                       matched_config_sha256=sha(config_path('matched.yaml'))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('fields',nargs='+')
    p.add_argument('--workers', type=int, choices=(1,2), default=1)
    args = p.parse_args()
    for field_id in args.fields:
        acquire(field_id,args.workers)
