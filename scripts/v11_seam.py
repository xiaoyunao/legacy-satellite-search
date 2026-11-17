"""Check both native coadd masks on a real cut crossing the survey seam."""
from pathlib import Path
import os

import numpy as np
import yaml

from ls_satsearch.data import Field, load_bricks, make_area
from ls_satsearch.run import coverage_metrics, write_json


cfg = yaml.safe_load(Path('configs/v7/search.yaml').read_text())
root = Path(os.environ['LS_DR11_ROOT'])
field = Field(214.14,32.375,1.5,min(cfg['radii_arcmin'])/3,buffer=0)
bits = sum(1<<b for b in cfg['reject_maskbits'])
rasters, primary, details = {}, {}, {}
for region in ('north','south'):
    bricks = load_bricks(root,region)
    rasters[region], info = make_area(root,field,bricks,bits,cfg['coverage_subdivision'],region=region)
    primary[region], _ = make_area(root,field,bricks,bits,cfg['coverage_subdivision'],
                                   region=region,primary=True)
    details[region] = dict(native_core_deg2=coverage_metrics(field,rasters[region],cfg)[0],
                           primary_core_deg2=coverage_metrics(field,primary[region],cfg)[0],
                           missing_brick_products=len(info['area_bricks_missing_products']))
assert not np.any(primary['north'] & primary['south'])
out=Path('results/v11/footprint/seam_check.json')
overlap=coverage_metrics(field,rasters['north']&rasters['south'],cfg)[0]
union=coverage_metrics(field,primary['north']|primary['south'],cfg)[0]
write_json(out,dict(job=os.environ['SLURM_JOB_ID'],center=[field.ra,field.dec],width_deg=field.width,
                   before_split_overlap_deg2=overlap,after_split_overlap_deg2=0.,
                   effective_primary_union_deg2=union,by_region=details,
                   scope='Coadd exposure and mask seam test. This region is a geometry control.'))
