"""Check whether NOIRLab candidate visits were reused by DR11 at the candidate brick."""

import argparse
import json
import os
from pathlib import Path
import re

import fitsio
import numpy as np

from ls_satsearch.data import load_bricks
from ls_satsearch.run import sha, write_json


def run(archive, output):
    a=json.loads(archive.read_text())
    ra,dec=a['center_ra_dec']
    root=Path(os.environ['LS_DR11_ROOT'])
    bricks=load_bricks(root,'south')
    inside=((ra-bricks['RA1'])%360 < (bricks['RA2']-bricks['RA1'])%360)
    inside &= (dec>=bricks['DEC1'])&(dec<bricks['DEC2'])
    records=bricks[np.flatnonzero(inside)]
    if len(records)!=1:
        raise ValueError(f'Expected one primary positional brick, saw {len(records)}')
    name=records[0]['BRICKNAME'].strip()
    ccds=root/'south'/'coadd'/name[:3]/name/f'legacysurvey-{name}-ccds.fits'
    table=fitsio.read(ccds,ext=1,lower=True)
    camera=np.char.strip(table['camera'].astype('U'))
    bands=np.char.strip(table['filter'].astype('U'))
    known=set(table['expnum'][(camera=='decam')&(bands=='g')])
    visits=[]
    for row in a['archives']['NOIRLab g']['results']['g_visits']:
        match=re.search(r'DECam_(\d+)',row['original_filename'])
        if match is None:
            continue
        exp=int(match[1])
        visits.append(dict(row,expnum=exp,in_primary_dr11_brick=exp in known))
    write_json(output,dict(job=os.getenv('SLURM_JOB_ID'),center_ra_dec=[ra,dec],brick=name,
               ccd_file=str(ccds),input_sha256=sha(ccds),dr11_g_exposures=sorted(known),
               noirlab_visits=visits,
               scope='The coadd CCD table applies to the primary brick. A nonmatching visit '
                     'still needs a detector-level footprint, product availability and depth check.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
