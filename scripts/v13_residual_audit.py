"""Account for South PS1 proxy pixels left outside the measured raster union."""
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import load_bricks, ownership, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.fields import Census
from ls_satsearch.regional_pilot import brick_covered, previous_cores
from ls_satsearch.run import settings, sha, write_csv, write_json
from v12_footprint import observed


if __name__ == '__main__':
    root,data,_=settings()
    grid=HEALPix(nside=256,order='ring')
    lon,lat=grid.healpix_to_lonlat(np.arange(grid.npix))
    ra,dec=lon.deg,lat.deg
    take=regional_primary(ra,dec,'south') & Census(data).accept(ra,dec,3)
    ra,dec=ra[take],dec[take]
    take=abs(SkyCoord(ra,dec,unit='deg').galactic.b.deg)>=25
    ra,dec=ra[take],dec[take]
    b=load_bricks(root,'south')
    quality=(b['PSFDEPTH_G']>0)&(b['PSFDEPTH_R']>0)&(b['EBV']<.1)
    quality &= np.isfinite(b['PSFSIZE_G']+b['PSFSIZE_R'])
    take=brick_covered(ra,dec,cKDTree(unit(b['RA'],b['DEC'])),b,quality)
    ra,dec=ra[take],dec[take]
    only_ps1={survey:np.full(len(ra),survey==3,dtype=bool) for survey in (1,2,3)}
    _,scanned,_=observed(data,ra,dec,'v13',only_ps1)
    history=sorted(Path('configs').glob('v1[12]/cohorts/*/fields.yaml'))
    history += [Path(f'configs/{v}/cohorts/south_ps1/fields.yaml') for v in ('v12g','v13')]
    cores,hashes=previous_cores(history)
    previous=np.zeros(len(ra),dtype=bool)
    for center,half,lo,hi in cores:
        previous |= (abs((ra-center+180)%360-180)<half)&(dec>=lo)&(dec<hi)
    path=Path('configs/v13r/cohorts/south_ps1/fields.yaml')
    assigned=np.zeros(len(ra),dtype=bool)
    for field in yaml.safe_load(path.read_text())['fields']:
        assigned |= ownership(ra,dec,field['ownership'])
    output=Path('results/v13/atlas')
    output.mkdir(exist_ok=True,parents=True)
    cell=grid.pixel_area.to_value(u.deg**2)
    rows=[]
    for category,mask in (
        ('measured_search_raster',scanned),
        ('outside_valid_raster_in_prior_core_geometry',~scanned&previous),
        ('outside_valid_raster_in_residual_ownership',~scanned&~previous&assigned),
        ('outside_registered_geometry',~scanned&~previous&~assigned),
    ):
        rows.append(dict(category=category,pixels=int(mask.sum()),proxy_deg2=mask.sum()*cell))
    write_csv(output/'south_ps1_residual_audit.csv',rows)
    write_json(output/'south_ps1_residual_audit.json',dict(job=os.getenv('SLURM_JOB_ID'),
               nside=grid.nside,prior_geometry_hashes=hashes,residual_geometry_sha256=sha(path),
               scope='The geometry classes distinguish missing valid search raster from absences in registration. '
               'The earlier registration set includes known fields and alternate census layers; its pixels '
               'may lack South PS1 coverage after their original masks.'))
