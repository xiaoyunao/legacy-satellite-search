"""Crossmatch each priority group independently with public catalogue summaries."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from astropy.coordinates import SkyCoord

import novelty_audit as archive
from ls_satsearch.run import read_csv, write_csv


CATALOGS = (
    ('Hunt & Reffert','J/A+A/686/A42/clusters','RA_ICRS','DE_ICRS','Name',
     [('-out','ID,Name,RA_ICRS,DE_ICRS')]),
    ('VizieR Local Group dwarf systems','J/AJ/144/4/catalog','_RAJ2000','_DEJ2000','Name',
     [('-out.add','_RAJ,_DEJ')]),
    ('VizieR Milky Way globulars','VII/202/catalog','_RAJ2000','_DEJ2000','ID',
     [('-out.add','_RAJ,_DEJ')]),
)


def parse_catalog(payload, ra, dec, name, sep):
    rows=archive.parse(payload,sep)
    if not rows or not {ra,dec,name}<=set(rows[0]):
        raise ValueError('Unexpected public catalogue schema')
    return archive.with_coords(rows,ra,dec)


def load_catalogs():
    calls=[(label,version,ra,dec,name,'\t',archive.asu(version,options))
           for label,version,ra,dec,name,options in CATALOGS]
    calls.append(('Unified Cluster Catalogue','260615 (Zenodo 20705026)',
                  'RA_ICRS','DE_ICRS','Name(s)',',',archive.UCC))
    result=[]
    for label,version,ra,dec,name,sep,url in calls:
        meta=dict(dataset=label,version=version,source=url)
        alternatives=[url,url.replace('vizier.cfa.harvard.edu','vizier.cds.unistra.fr')]
        for site in dict.fromkeys(alternatives):
            try:
                payload=archive.fetch(site)
                rows=parse_catalog(payload,ra,dec,name,sep)
                result.append((dict(meta,source=site,status='complete',input_sha256=sha256(payload).hexdigest()),
                               rows,ra,dec,name))
                break
            except (OSError,ValueError) as error:
                failed=dict(meta,source=site,status=type(error).__name__,reason=str(error))
        else:
            result.append((failed,[],ra,dec,name))
    for path in sorted(archive.LITERATURE.glob('*.csv')):
        data=path.read_bytes()
        parsed=parse_catalog(data,'ra','dec','name',',')
        result.append((dict(dataset=path.stem,version='pinned repository input',source=str(path),
                      input_sha256=sha256(data).hexdigest(),status='complete'),parsed,'ra','dec','name'))
    return result


def simbad(group, center):
    ra,dec=center.ra.deg,center.dec.deg
    cone=f"1=CONTAINS(POINT('ICRS',b.ra,b.dec),CIRCLE('ICRS',{ra},{dec},0.5))"
    url=archive.tap(f'SELECT TOP 4000 b.main_id,b.otype,b.ra,b.dec,b.coo_bibcode FROM basic AS b WHERE {cone}')
    shared=dict(group_id=group,dataset='SIMBAD all types',version='live 30 arcmin cone',source=url)
    try:
        data=archive.fetch(url)
        rows=archive.parse(data)
        if len(rows)>=4000 or (rows and not {'main_id','ra','dec','otype'}<=set(rows[0])):
            raise ValueError('SIMBAD cone truncated or unreadable')
        shared.update(status='complete',input_sha256=sha256(data).hexdigest())
        if not rows:
            return [dict(shared,rows=0,within_5arcmin=0,within_30arcmin=0)]
        measured=archive.ordinal_summary(center,rows,'ra','dec','main_id',**shared)
        distance=archive.separations(center,rows,'ra','dec')
        kind=Counter(r['otype'] for r,d in zip(rows,distance) if d<=5)
        by_type=[dict(measured, dataset='SIMBAD object type',otype=t,total_5arcmin=k)
                 for t,k in sorted(kind.items())]
        return [measured,*by_type]
    except (OSError,ValueError,KeyError,IndexError) as error:
        return [dict(shared,status=type(error).__name__,reason=str(error))]


def probe(row,catalogs,published):
    group=row['group_id']
    target=SkyCoord(float(row['ra_deg']),float(row['dec_deg']),unit='deg')
    records=[]
    for meta,data,ra,dec,name in catalogs:
        if data:
            records.append(archive.ordinal_summary(target,data,ra,dec,name,group_id=group,**meta))
        else:
            records.append(dict(meta,group_id=group))
    for item in published:
        pos=SkyCoord(float(item['ra_deg']),float(item['dec_deg']),unit='deg')
        records.append(dict(group_id=group,dataset='published coordinate',status='complete',
                            nearest_name=item['object'],nearest_arcmin=target.separation(pos).arcmin,
                            source=item['source'],version=item['coordinate_definition']))
    return records+simbad(group,target)


def run(output):
    cases=[]
    for f in sorted(Path('results/v12/discovery').glob('*/*/main/priority_modes.csv')):
        cases.extend(r for r in read_csv(f) if r['representative']=='True')
    public=read_csv(Path('results/summary/novelty_published_candidates.csv'))
    public+=read_csv(Path('configs/v12/recent_public_sources.csv'))
    if not cases:
        raise ValueError('No completed priority lists')
    catalogs=load_catalogs()
    when=datetime.now(timezone.utc).isoformat(timespec='seconds')
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows=[dict(r,checked_utc=when) for result in pool.map(lambda row:probe(row,catalogs,public),cases)
              for r in result]
    output.parent.mkdir(exist_ok=True,parents=True)
    write_csv(output,rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    run(p.parse_args().output)
