"""Bounded public TAP schema discovery; no coverage inference from request failures."""
import csv
from datetime import datetime,timezone
import io
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from ls_satsearch.run import write_csv,write_json


def run():
    out=Path('results/v14/repeat_full/euclid_coverage');out.mkdir(parents=True,exist_ok=True)
    endpoint='https://eas.esac.esa.int/tap-server/tap/sync'
    query="SELECT TOP 200 table_name,description FROM TAP_SCHEMA.tables WHERE table_name LIKE '%mer%' OR table_name LIKE '%dr1%' OR table_name LIKE '%obscore%'"
    payload=urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query)).encode()
    result=dict(utc=datetime.now(timezone.utc).isoformat(),endpoint=endpoint,query=query,
        scope='Public schema metadata only. No per-source catalogue retrieved; no sky-coverage conclusion before valid cone/image metadata queries.')
    try:
        req=Request(endpoint,data=payload,headers={'User-Agent':'legacy-satellite-search/metadata-probe'})
        with urlopen(req,timeout=45) as response:
            raw=response.read(1000001)
            result.update(http_status=response.status,content_type=response.headers.get('Content-Type'))
        if len(raw)>1000000:raise ValueError('Bounded schema reply exceeded size limit')
        text=raw.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or 'table_name' not in reader.fieldnames:
            raise ValueError('Response is not the requested table-name CSV')
        rows=list(reader)
        if len(rows)>=200:raise ValueError('Schema query reached row cap')
        write_csv(out/'tables.csv',rows,keys=('table_name','description'))
        result.update(state='schema_received',tables=len(rows))
    except Exception as error:
        result.update(state='request_failed_coverage_unknown',error_type=type(error).__name__,error=str(error)[:300])
    write_json(out/'schema_probe.json',result)
    print({k:result[k] for k in ('state',)})


if __name__=='__main__':run()
