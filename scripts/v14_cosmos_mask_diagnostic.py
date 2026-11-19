import os,json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy_healpix import HEALPix
from ls_satsearch.run import settings,field_cache,write_json
from ls_satsearch.data import load_bricks,sample_pixels
import yaml
assert os.getenv('SLURM_JOB_ID')
os.environ['LS_SAT_CONFIG_DIR']='configs/v14_cosmos_reference'
root,data,cfg=settings();m=yaml.safe_load(Path('configs/v14_cosmos_reference/matched.yaml').read_text());s=dict(m['fields'][0],width=m['width_deg'],buffer_arcmin=0)
f,cat,area,inputs=field_cache(root,data,s,cfg,load_bricks(root,'south'))
a=json.loads(Path('results/v14/repeat_full/cosmos_reference/acquisition.json').read_text());r=np.load(a['subset_path']);x,y=f.xy(r['RA'],r['DEC']);core=(abs(x)<f.width*30)&(abs(y)<f.width*30);ls=area[sample_pixels(f,area,x,y)]
with fits.open(data/'resources/ps1/ps1d_mask_v2.1.fits',memmap=True) as hd:
 h=HEALPix(nside=4096,order='ring');v=hd[1].data['T'].reshape(-1)[h.lonlat_to_healpix(r['RA']*u.deg,r['DEC']*u.deg)].astype('i8')
 out=dict(job=os.environ['SLURM_JOB_ID'],core_refs=int(core.sum()),LS_mask_refs=int((core&ls).sum()),LS_mask_cells=int(area.sum()),PS1_bit_counts={str(b):int((core&ls&((v&(1<<b))!=0)).sum()) for b in range(8)},PS1_value_counts={str(k):int(n) for k,n in zip(*np.unique(v[core&ls],return_counts=True))},LS_inputs=inputs)
write_json(Path('results/v14/repeat_full/cosmos_reference/mask_diagnostic.json'),out);print(out['PS1_bit_counts'])
