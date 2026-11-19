"""Check independent public imaging at the three frozen physical-background cores."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path

from ls_satsearch.run import read_csv,write_json
from scripts.v14_cadc0706_retry import QUERY,query


def run():
    sites=read_csv(Path('configs/v14_repeat/image_fields.csv'))
    def check(site):
        sql=QUERY.replace('165.61216974832084,31.892121971411218',site['ra_deg']+','+site['dec_deg'])
        result=query(site['field'],'GET',sql)
        return dict(site=site['field'],ra_deg=float(site['ra_deg']),dec_deg=float(site['dec_deg']),
                    radius_deg=.06,**result)
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(check,sites))
    out=Path('results/v14/repeat_full/cadc_reference_coverage.json')
    write_json(out,dict(utc=datetime.now(timezone.utc).isoformat(),fields=rows,
        scope='Public image metadata intersecting a 3.6 arcmin cone at each frozen injection stamp. Intersections do not establish full core support, depth, independence of processing/exposures or truth labels. Query failures remain unknown; no new physical background or parameter grid selected.'))
    print([(r['site'],r['status'],len(r.get('rows',[]))) for r in rows])


if __name__=='__main__':run()
