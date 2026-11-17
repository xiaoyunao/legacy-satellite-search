"""Check public image archives at the new round-12 priority position."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from astropy.coordinates import SkyCoord
import yaml

from audit_survey63_archives import FIELDS, gemini, hsc_field, mast, noirlab, smoka
from ls_satsearch.run import write_json


def run(plan, output):
    spec=yaml.safe_load(plan.read_text())
    coord=(spec['ra_deg'],spec['dec_deg'])
    core=spec['center_aperture_arcmin']
    center=SkyCoord(*coord,unit='deg')
    callbacks={'NOIRLab g':(noirlab,coord),'Gemini North':(gemini,coord),
               'HST and JWST':(mast,coord),'SMOKA HSC-g':(smoka,(center,'Shot',55))}
    callbacks.update({f'HSC SSP {field}':(hsc_field,(field,center,core)) for field in FIELDS})
    report={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending={key:pool.submit(fn,*args) for key,(fn,args) in callbacks.items()}
        for key,result in pending.items():
            try:
                report[key]=dict(status='query_complete',results=result.result())
            except (OSError,ValueError,KeyError) as err:
                report[key]=dict(status='query_failed',reason=str(err))
    output.parent.mkdir(exist_ok=True,parents=True)
    write_json(output,dict(center_ra_dec=coord,core_radius_arcmin=core,archives=report,
                  scope='Metadata geometry only. Overlap, product access and depth require actual calibrated pixels.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    run(a.plan,a.output)
