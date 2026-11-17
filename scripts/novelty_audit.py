"""Run reproducible coordinate queries against public literature catalogues."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
import numpy as np
import yaml

ASU = 'https://vizier.cfa.harvard.edu/viz-bin/asu-tsv'
SIMBAD = 'https://simbad.harvard.edu/simbad/sim-tap/sync'
UCC = 'https://zenodo.org/records/20705026/files/UCC_cat.csv?download=1'
LITERATURE = Path('references/codex_benchmark_sources')


def asu(table, options=()):
    return ASU+'?'+urlencode([('-source',table),('-out.max','unlimited'),*options])


def tap(query):
    return SIMBAD+'?'+urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))


def fetch(url):
    with urlopen(url,timeout=40) as response:
        data=response.read(25_000_001)
    if len(data)>25_000_000:
        raise ValueError('Unbounded catalogue response')
    return data


def parse(data, separator=','):
    raw=data.decode('utf-8-sig')
    reader=csv.DictReader((line for line in StringIO(raw) if line.strip() and not line.startswith('#')),
                          delimiter=separator)
    return list(reader)


def write(path, rows, fieldnames=None):
    with path.open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames or list(rows[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def with_coords(rows,ra,dec):
    valid=[]
    for row in rows:
        try:
            float(row[ra])
            float(row[dec])
        except (ValueError,TypeError):
            continue
        valid.append(row)
    return valid


def separations(center, rows, ra, dec):
    pos=SkyCoord([float(r[ra]) for r in rows],[float(r[dec]) for r in rows],unit='deg')
    return center.separation(pos).arcmin


def ordinal_summary(center, data, ra, dec, name, **metadata):
    valid=with_coords(data,ra,dec)
    d=separations(center,valid,ra,dec)
    i=int(d.argmin())
    return dict(**metadata,rows=len(valid),within_5arcmin=int((d<=5).sum()),
                within_30arcmin=int((d<=30).sum()),nearest_name=valid[i][name].strip(),
                nearest_arcmin=float(d[i]))


def run(out, hunt_cross_response=None, plan=Path('configs/v6/followup.yaml')):
    target=yaml.safe_load(plan.read_text())
    ra,dec=target['ra_deg'],target['dec_deg']
    center=SkyCoord(ra,dec,unit='deg')
    when=datetime.now(timezone.utc).isoformat(timespec='seconds')
    out.mkdir(exist_ok=True,parents=True)
    order=[]
    def add(dataset,version,url,raw,parsed,raname,decname,name):
        coordinates={r.strip() for r in (raname,decname,name)}
        if not parsed or not coordinates<=set(parsed[0]):
            raise ValueError(f'Missing expected schema for {dataset}')
        order.append(ordinal_summary(center,parsed,raname,decname,name,dataset=dataset,
                     version=version,checked_utc=when,source=url,
                     input_sha256=hashlib.sha256(raw).hexdigest()))

    for cat,table,c_ra,c_dec,c_name,options in [
        ('Hunt & Reffert','J/A+A/686/A42/clusters','RA_ICRS','DE_ICRS','Name',
            [('-out','ID,Name,RA_ICRS,DE_ICRS')]),
        ('VizieR Local Group dwarf systems','J/AJ/144/4/catalog','_RAJ2000','_DEJ2000','Name',
            [('-out.add','_RAJ,_DEJ')]),
        ('VizieR Milky Way globulars','VII/202/catalog','_RAJ2000','_DEJ2000','ID',
            [('-out.add','_RAJ,_DEJ')]),
    ]:
        source=asu(table,options)
        raw=fetch(source)
        add(cat,table,source,raw,parse(raw,'\t'),c_ra,c_dec,c_name)
    raw=fetch(UCC)
    add('Unified Cluster Catalogue','260615 (Zenodo 20705026)',UCC,raw,parse(raw),
        'RA_ICRS','DE_ICRS','Name(s)')
    hunt=order[0]
    cross_url=asu('J/A+A/686/A42/crossma')
    cross_data=hunt_cross_response.read_bytes() if hunt_cross_response else fetch(cross_url)
    cross_rows=parse(cross_data,'\t')
    numbered=[r for r in cross_rows if r['ID'].strip().isdigit()]
    if len(numbered)<5000:
        raise ValueError('Incomplete Hunt cross-ID table')
    write(out/'novelty_hunt_cross_id.csv',[dict(checked_utc=when,source=cross_url,
          input_sha256=hashlib.sha256(cross_data).hexdigest(),literature_rows_colocated_by_internal_id=len(numbered),
          associated_clusters_in_30arcmin=hunt['within_30arcmin'])])

    for path in sorted(LITERATURE.glob('*.csv')):
        raw=path.read_bytes()
        add(path.stem,'pinned repository input',str(path),raw,parse(raw),'ra','dec','name')

    def cone(radius):
        return f"1=CONTAINS(POINT('ICRS',b.ra,b.dec),CIRCLE('ICRS',{ra},{dec},{radius}))"

    source=tap(f'SELECT TOP 4000 b.main_id,b.otype,b.ra,b.dec,b.coo_bibcode,b.oid FROM basic AS b WHERE {cone(.5)}')
    raw=fetch(source)
    sim=parse(raw)
    if len(sim)==4000:
        raise ValueError('SIMBAD 30 arcmin cone is truncated')
    add('SIMBAD all types','live basic table, 30 arcmin query',source,raw,sim,'ra','dec','main_id')
    near=tap(f'SELECT TOP 12000 b.oid,i.id FROM basic AS b JOIN ident AS i ON b.oid=i.oidref WHERE {cone(.5)}')
    identifiers=parse(fetch(near))
    if len(identifiers)==12000:
        raise ValueError('SIMBAD alias cone is truncated')
    distance=separations(center,sim,'ra','dec')
    grouped=Counter((r['otype'],d<=5) for r,d in zip(sim,distance))
    counts=[dict(otype=k,total_30arcmin=grouped[k,True]+grouped[k,False],
                 total_5arcmin=grouped[k,True]) for k in sorted({r['otype'] for r in sim})]
    write(out/'novelty_simbad_types.csv',counts)
    nearby=[
        dict(main_id=r['main_id'],otype=r['otype'],distance_arcmin=float(distance[i]),
             coo_bibcode=r['coo_bibcode'],aliases=' | '.join(sorted(a['id'] for a in identifiers if a['oid']==r['oid'])),
             checked_utc=when,alias_query=near)
        for i,r in enumerate(sim)
    ]
    nearby.sort(key=lambda r:r['distance_arcmin'])
    write(out/'novelty_simbad_5arcmin.csv',[r for r in nearby if r['distance_arcmin']<=5],
          list(nearby[0]))
    write(out/'novelty_simbad_30arcmin.csv',nearby)
    write(out/'novelty_catalog_checks.csv',order)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('results/summary'))
    parser.add_argument('--hunt-cross-response',type=Path,help='Previously downloaded response to the documented cross-ID query')
    parser.add_argument('--plan',type=Path,default=Path('configs/v6/followup.yaml'))
    args=parser.parse_args()
    run(args.output,args.hunt_cross_response,args.plan)
