"""Bounded metadata checks for selected, visually inspected priority positions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from scripts.audit_survey63_archives import noirlab
from scripts.v14_cadc0706_retry import query
from ls_satsearch.run import read_csv, write_json


def run(case_ids):
    cases = {r['case_id']: r for r in read_csv(Path('results/v14/shortlist/cases.csv'))}
    out = Path('results/v14/shortlist/archive_checks')
    out.mkdir(exist_ok=True)
    for case_id in case_ids:
        case = cases[case_id]
        if case['queue'] != 'priority':
            raise ValueError('Do not unblind audit positions through archive queries')
        # The fixed discovery centre defines a broad metadata ROI; fitted-mode
        # containment and independence from LS exposures require pixel checks.
        ra, dec = float(case['ra_deg']), float(case['dec_deg'])
        adql = f"""SELECT TOP 300 O.collection,O.observationID,O.instrument_name,P.planeURI,
P.productID,P.calibrationLevel,P.energy_bandpassName,P.time_exposure,P.dataRelease
FROM caom2.Observation AS O JOIN caom2.Plane AS P ON O.obsID=P.obsID
WHERE INTERSECTS(CIRCLE('ICRS',{ra},{dec},0.15),P.position_bounds)=1
AND P.dataProductType='image'
AND O.collection IN ('CFHT','CFHTMEGAPIPE','CFHTTERAPIX','GEMINI','HST','HSTHLA','SUBARU')"""
        with ThreadPoolExecutor(max_workers=2) as pool:
            cadc = pool.submit(query, 'shortlist_roi', 'GET', adql)
            noir = pool.submit(noirlab, ra, dec)
            report = dict(CADC=cadc.result())
            try:
                report['NOIRLab_g'] = dict(status='complete', result=noir.result())
            except Exception as exc:
                report['NOIRLab_g'] = dict(status='failed', error=f'{type(exc).__name__}: {exc}')
        write_json(out / f'{case_id}.json', dict(case_id=case_id, discovery_ra_dec=[ra, dec],
            utc=datetime.now(timezone.utc).isoformat(), archives=report,
            scope='Metadata query only. Failed services leave coverage unresolved. An overlapping product is not yet deep, full-core or independent of LS. No image download or population confirmation is implied.'))
        print(case_id, {key: value['status'] for key, value in report.items()}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_ids', nargs='+')
    run(parser.parse_args().case_ids)
