"""Retry bounded public CADC metadata queries without inferring absent coverage on errors."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ls_satsearch.run import write_json

ENDPOINT = 'https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync'
QUERY = """SELECT TOP 300 O.collection,O.observationID,O.instrument_name,P.planeURI,
P.productID,P.calibrationLevel,P.energy_bandpassName,P.time_exposure,P.dataRelease
FROM caom2.Observation AS O JOIN caom2.Plane AS P ON O.obsID=P.obsID
WHERE INTERSECTS(CIRCLE('ICRS',165.61216974832084,31.892121971411218,0.06),P.position_bounds)=1
AND P.dataProductType='image'
AND O.collection IN ('CFHT','CFHTMEGAPIPE','CFHTTERAPIX','GEMINI','HST','HSTHLA','SUBARU')"""


def query(label, method, query):
    parameters=urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))
    url=ENDPOINT+('?' + parameters if method=='GET' else '')
    record=dict(label=label,method=method,url=url,query=query)
    headers={'User-Agent':'legacy-satellite-search public imaging audit','Accept':'text/csv'}
    if method=='POST':
        headers['Content-Type']='application/x-www-form-urlencoded'
    request=Request(url,data=parameters.encode() if method=='POST' else None,headers=headers)
    try:
        with urlopen(request,timeout=35) as response:
            body=response.read(16_000_001)
            record.update(http_status=response.status,final_url=response.url)
        if len(body)>16_000_000:
            raise ValueError('Metadata response exceeded the bounded query budget')
        reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
        rows=list(reader)
        if 'collection' not in (reader.fieldnames or []):
            raise ValueError('CADC did not return the expected collection CSV column')
        if len(rows)>=300:
            raise ValueError('ROI response reached the row cap')
        record.update(status='complete',rows=rows,sha256=sha256(body).hexdigest())
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc))
    return record


def run(output, origin):
    work=[('roi_get','GET',QUERY),('roi_post','POST',QUERY),
          ('service_health','GET','SELECT TOP 1 collection FROM caom2.Observation')]
    attempts=[]
    output.parent.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending=[pool.submit(query,*spec) for spec in work]
        for future in as_completed(pending):
            record=future.result();attempts.append(record)
            write_json(output,dict(utc=datetime.now(timezone.utc).isoformat(),origin=origin,
                       ra_deg=165.61216974832084,dec_deg=31.892121971411218,
                       attempts=attempts,coverage_status='evaluated' if any(
                           r['label'].startswith('roi_') and r['status']=='complete' for r in attempts)
                           else 'unknown_due_to_service_errors'))
            print(record['label'],record['status'],len(record.get('rows',[])),record.get('error',''),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--origin',required=True)
    args=p.parse_args();run(args.output,args.origin)
