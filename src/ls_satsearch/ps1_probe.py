"""Exercise access to real PS1 stack photometry and its native PARSEC template."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import yaml

from .run import read_csv, settings, write_csv
from .search import load_isochrone

URL='https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/stack'
COLS=('objID','raStack','decStack','primaryDetection','gPSFMag','rPSFMag',
      'gPSFMagErr','rPSFMagErr','rKronMag')


def main(fresh=None):
    _,data,cfg=settings()
    dest=data/'resources/ps1'
    native=data/'resources/isochrones/ps1'/Path(cfg['isochrone']).parent.name/Path(cfg['isochrone']).name
    model=load_isochrone(native,bands=('gP1','rP1'))
    known=read_csv(Path('references/benchmarks.csv'))
    names=('Pegasus_IV','Leo_Minor_I','Aquarius_IV')
    targets=[(name,'benchmark',row['ra_deg'],row['dec_deg']) for name in names
             for row in known if row['name']==name]
    if fresh is not None:
        fields=yaml.safe_load(fresh.read_text())['fields']
        for role in ('pilot_dev','pilot_eval'):
            field=next(r for r in fields if r['role']==role and r['layer']=='ordinary')
            targets.append((field['id'],role,field['ra'],field['dec']))
    result=[]
    for name,role,ra,dec in targets:
        request=dict(ra=ra,dec=dec,radius=.35,primaryDetection=1,
                     columns='['+','.join(COLS)+']',pagesize=50000)
        query=URL+'.csv?'+urlencode(request)
        path=dest/f'{name}-035deg.csv'
        if not path.exists():
            with urlopen(query,timeout=90) as stream:
                response=stream.read()
            path.with_suffix('.tmp').write_bytes(response)
            path.with_suffix('.tmp').replace(path)
            time.sleep(1)
        with path.open() as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not set(COLS)<=set(reader.fieldnames):
                raise ValueError(f'Unexpected PS1 response schema for {name}')
            rows={r['objID']:r for r in reader}
        gr=np.array([[float(r[k]) for k in COLS[4:]] for r in rows.values()])
        valid=np.all((gr[:,:2]>0)&(gr[:,:2]<35),axis=1) & np.all((gr[:,2:4]>0)&(gr[:,2:4]<.217),axis=1)
        morphology=(gr[:,4]>0)&(gr[:,1]-gr[:,4]<.05)
        result.append(dict(name=name,role=role,release='PS1 DR2 stack',radius_deg=.35,unique_rows=len(rows),
                           possible_page_cap=len(rows)>=50000,valid_gr=int(valid.sum()),
                           morphology_proxy_gr=int((valid&morphology).sum()), query=query,
                           native_template_rows=len(model[0]), native_template_sha256=hashlib.sha256(
                               native.read_bytes()).hexdigest(), input_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print(name,len(rows),int((valid&morphology).sum()),flush=True)
    write_csv(Path('results/summary/ps1_real_catalog_probe.csv'),result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh',type=Path)
    main(parser.parse_args().fresh)
