"""Count public Euclid sources at calibration/candidate cones with a known positive control."""
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime,timezone
import io
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from ls_satsearch.run import read_csv,write_csv,write_json


ENDPOINT='https://eas.esac.esa.int/tap-server/tap/sync'


def query_count(site):
    name,ra,dec,radius=site
    query=("SELECT COUNT(*) AS n FROM dr1.mer_catalogue_wide_survey WHERE "
        f"1=CONTAINS(POINT('ICRS',right_ascension,declination),CIRCLE('ICRS',{ra},{dec},{radius}))")
    record=dict(target=name,ra_deg=ra,dec_deg=dec,radius_deg=radius,query=query)
    try:
        req=Request(ENDPOINT,data=urlencode(dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query)).encode())
        with urlopen(req,timeout=45) as response:raw=response.read(100001)
        if len(raw)>100000:raise ValueError('Count reply exceeds metadata limit')
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        if len(rows)!=1 or 'n' not in {k.lower() for k in rows[0]}:raise ValueError('Invalid count response')
        count=int(next(v for k,v in rows[0].items() if k.lower()=='n'))
        record.update(state='count_received',source_count=count)
    except Exception as error:
        record.update(state='query_failed_coverage_unknown',error_type=type(error).__name__,error=str(error)[:250])
    return record


def run():
    sites=[(r['field'],float(r['ra_deg']),float(r['dec_deg']),1/3)
           for r in read_csv(Path('configs/v14_repeat/image_fields.csv'))]
    sites += [('candidate_0706',165.61216974832084,31.892121971411218,.06),
              ('positive_control_euclid_ufss_dr1_1',196.1542,75.5724,.1)]
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(query_count,sites))
    out=Path('results/v14/repeat_full/euclid_coverage');out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'cone_counts.csv',rows)
    control=next(r for r in rows if r['target'].startswith('positive_control'))
    write_json(out/'cone_probe.json',dict(utc=datetime.now(timezone.utc).isoformat(),endpoint=ENDPOINT,
        catalogue='dr1.mer_catalogue_wide_survey',positive_control_valid=control.get('source_count',0)>0,
        successful_counts=sum(r['state']=='count_received' for r in rows),
        scope='Public count queries only. Positive source count establishes some catalogue coverage, not complete core coverage, adequate depth or clean point-source truth. Zero or failed responses are not interchangeable. Check the known published-system control before interpreting nulls. Raw catalogues/images, if needed, must be retrieved to NERSC.'))
    print([(r['target'],r['state'],r.get('source_count')) for r in rows])


if __name__=='__main__':run()
