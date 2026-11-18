"""Bounded public image archive queries at the frozen compact candidate position."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import io
import json
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
import yaml

from audit_survey63_archives import FIELDS, gemini, hsc_field, mast, smoka
from ls_satsearch.run import write_json, write_csv

RA, DEC = 165.61216974832084, 31.892121971411218


def fetch(url, payload=None):
    with urlopen(url, payload, timeout=50) as f:
        return f.read(16_000_001)


def cadc():
    endpoint='https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync'
    query=f"""SELECT TOP 300 O.collection,O.observationID,O.instrument_name,P.planeURI,
 P.productID,P.calibrationLevel,P.energy_bandpassName,P.time_exposure,P.dataRelease
 FROM caom2.Observation AS O JOIN caom2.Plane AS P ON O.obsID=P.obsID
 WHERE INTERSECTS(CIRCLE('ICRS',{RA},{DEC},0.06),P.position_bounds)=1
 AND P.dataProductType='image' AND O.collection IN ('CFHT','CFHTMEGAPIPE','CFHTTERAPIX','GEMINI','HST','HSTHLA','SUBARU')"""
    url=endpoint+'?'+urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))
    data=fetch(url).decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(data)))
    if not rows or 'collection' not in rows[0]:
        if 'collection' not in data.splitlines()[0]:
            raise ValueError(data[:350])
    if len(rows)==300:
        raise ValueError('CADC result truncated')
    return dict(url=url,rows=rows)


def noir():
    url='https://astroarchive.noirlab.edu/api/sia/vohdu?'+urlencode(dict(POS=f'{RA},{DEC}',SIZE='.13',VERB=3,format='json'))
    head,*rows=json.loads(fetch(url))
    if head['RESULTS']['MORE'] or len(rows)!=head['RESULTS']['COUNT']:
        raise ValueError('NOIRLab result truncated')
    keys=('original_filename','file_dateobs','instrument','filter','exposure','proc_type','prod_type','access_url','archive_filename','md5sum','obs_type','proposal_id','url','hdu_idx')
    return dict(url=url,rows=[{k:r.get(k) for k in keys if k in r} for r in rows])


def ps1():
    url='https://ps1images.stsci.edu/cgi-bin/ps1filenames.py?'+urlencode(dict(ra=RA,dec=DEC,filters='gr',type='stack'))
    page=fetch(url).decode()
    reader=csv.DictReader(io.StringIO(page),delimiter=' ',skipinitialspace=True)
    rows=list(reader)
    if 'filename' not in (reader.fieldnames or []):
        raise ValueError(page[:200])
    for r in rows:
        r['cutout_url']='https://ps1images.stsci.edu/cgi-bin/fitscut.cgi?'+urlencode(dict(ra=RA,dec=DEC,size=1440,format='fits',red=r['filename']))
    return dict(url=url,rows=rows,pixel_arcsec=.25)


def sdss():
    url='https://skyserver.sdss.org/dr18/SkyServerWS/SIAP/getSIAP?'+urlencode(dict(POS=f'{RA},{DEC}',SIZE='.1',FORMAT='image/fits',BANDPASS='gr'))
    from astropy.io.votable import parse_single_table
    data=fetch(url).decode('utf-8-sig')
    data=re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', data, count=1)
    table=parse_single_table(io.BytesIO(data.encode())).to_table()
    return dict(url=url,rows=[{k:str(row[k]) for k in table.colnames} for row in table])


def run():
    out=Path('results/v14/0706')
    out.mkdir(exist_ok=True,parents=True)
    center=SkyCoord(RA,DEC,unit='deg')
    work={'CADC':cadc,'NOIRLab':noir,'PS1_images':ps1,'SDSS_images':sdss,
          'HST_JWST':lambda:mast(RA,DEC),'Gemini':lambda:gemini(RA,DEC),
          'SMOKA_HSC':lambda:smoka(center,'Shot',55)}
    work.update({f'HSC_{name}':lambda name=name:hsc_field(name,center,.75) for name in FIELDS})
    result={}
    with ThreadPoolExecutor(max_workers=8) as executor:
        pending={executor.submit(fn):name for name,fn in work.items()}
        for future in as_completed(pending):
            name=pending[future]
            try:
                value=future.result()
                result[name]=dict(status='complete',**value)
            except Exception as exc:
                result[name]=dict(status='failed',error=str(exc))
            write_json(out/'archive_audit.json',dict(utc=datetime.now(timezone.utc).isoformat(),ra_deg=RA,dec_deg=DEC,archives=result))
            status=result[name]
            print(name,status['status'],len(status.get('rows',[])),status.get('error',''),flush=True)


if __name__=='__main__':
    run()
