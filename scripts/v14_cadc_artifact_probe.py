"""Discover public CFHT stack artifacts for 0706; metadata only."""
import csv
from datetime import datetime,timezone
import io
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from ls_satsearch.run import write_csv,write_json


def run():
    out=Path('results/v14/0706/cadc_followup');out.mkdir(parents=True,exist_ok=True)
    query="""SELECT O.collection,O.observationID,P.productID,P.energy_bandpassName,
A.uri,A.productType,A.contentType,A.contentLength,A.contentChecksum
FROM caom2.Observation AS O JOIN caom2.Plane AS P ON O.obsID=P.obsID
JOIN caom2.Artifact AS A ON P.planeID=A.planeID
WHERE O.collection='CFHTMEGAPIPE' AND O.observationID='MegaPipe.281.244'
AND (P.energy_bandpassName='r.MP9602' OR P.energy_bandpassName='u.MP9302')"""
    endpoint='https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync'
    url=endpoint+'?'+urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query))
    report=dict(utc=datetime.now(timezone.utc).isoformat(),query=query,url=url)
    try:
        with urlopen(url,timeout=40) as response:raw=response.read(1000001)
        if len(raw)>1000000:raise ValueError('Artifact metadata size cap reached')
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if 'uri' not in (reader.fieldnames or []):raise ValueError('Artifact CSV schema unavailable')
        rows=list(reader);write_csv(out/'20261119-stack-artifacts.csv',rows)
        report.update(state='metadata_received',artifacts=len(rows),
            scope='Public artifact discovery only. No standard g product in the recovered ROI metadata; gri is a distinct broad filter. u/r stacks require actual WCS/weight/depth measurement before any stellar-population claim.')
    except Exception as error:report.update(state='failed',error=str(error)[:300])
    write_json(out/'20261119-stack-artifacts.json',report)
    print(report['state'],report.get('artifacts'),report.get('error',''))


if __name__=='__main__':run()
