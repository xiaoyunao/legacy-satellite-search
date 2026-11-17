"""Retrieve only the public calibrated CCD products listed for one exposure."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from shutil import copyfileobj
from urllib.request import urlopen

from ls_satsearch.run import sha, write_json


PRODUCTS={'image':'image','wtmap':'weight','dqmask':'dq'}


def run(archive, expnum, output):
    meta=json.loads(archive.read_text())['archives']['NOIRLab g']['results']
    with urlopen(meta['url'],timeout=45) as stream:
        payload=stream.read(4_000_001)
    if len(payload)>4_000_000:
        raise ValueError('Archive result too large')
    head,*rows=json.loads(payload)
    if head['RESULTS']['MORE'] or head['RESULTS']['COUNT']!=len(rows):
        raise ValueError('Incomplete NOIRLab HDU query')
    output.mkdir(exist_ok=True,parents=True)
    products=[]
    for row in rows:
        if (f'DECam_{expnum:08d}.fits.fz' not in row['original_filename']
                or row['proc_type']!='instcal' or row['prod_type'] not in PRODUCTS):
            continue
        url=row['url']
        if not re.fullmatch(r'https://astroarchive\.noirlab\.edu/api/retrieve/[a-f0-9]{32}/\?hdus=0,\d+',url):
            raise ValueError('Unexpected bounded NOIRLab retrieval URL')
        filename=f"{PRODUCTS[row['prod_type']]}-{int(row['hdu_idx'])}.fits"
        path=output/filename
        if not path.exists():
            temporary=path.with_suffix('.part')
            with urlopen(url,timeout=90) as response,temporary.open('wb') as f:
                copyfileobj(response,f)
            with temporary.open('rb') as f:
                if f.read(6)!=b'SIMPLE':
                    raise ValueError('Retrieved product is not FITS')
            temporary.replace(path)
        products.append(dict(filename=filename,sha256=sha(path),bytes=path.stat().st_size,
                             url=url,archive_full_product_md5=row['md5sum']))
    if not products:
        raise ValueError(f'No calibrated extension products for exposure {expnum}')
    write_json(output/'manifest.json',dict(expnum=expnum,query_sha256=hashlib.sha256(payload).hexdigest(),
               source_query=meta['url'],products=products,scope='Only selected HDU bytes were retrieved.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('expnum',type=int)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
