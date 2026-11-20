"""Inspect actual official PSF representations before any pixel injection."""
import json
import os
from pathlib import Path
import numpy as np
from astropy.io import fits
from ls_satsearch.run import sha,write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Native PSF audit requires Slurm')
    source=Path('results/v14/ps1_ipp/blank_pilot/stack_preflight_61622347.json')
    m=json.loads(source.read_text());rows=[]
    for band in 'grizy':
        image=m['image_ids_from_same_cell_DR2'][band]
        p=Path(m['raw_output_root'])/f'native_grizy.stk.{image}.psf'
        if sha(p)!=m['artifacts'][p.name]['sha256']:raise ValueError('Native PSF changed')
        with fits.open(p) as hd:
            kernel=np.squeeze(hd['PSF_MODEL'].data).astype(float)
        if kernel.ndim!=2 or not np.isfinite(kernel).all():raise ValueError('Invalid PSF representation')
        y,x=np.indices(kernel.shape);positive=np.maximum(kernel,0);mass=positive.sum()
        cx=(x*positive).sum()/mass;cy=(y*positive).sum()/mass
        rr=np.hypot(x-cx,y-cy)
        edge=(x<2)|(y<2)|(x>=kernel.shape[1]-2)|(y>=kernel.shape[0]-2)
        rows.append(dict(band=band,PSF_sha256=sha(p),shape=list(kernel.shape),sum=float(kernel.sum()),
            minimum=float(kernel.min()),maximum=float(kernel.max()),negative_pixels=int((kernel<0).sum()),
            negative_abs_fraction=float(-kernel[kernel<0].sum()/mass),positive_centroid_pixels=[float(cx),float(cy)],
            edge_two_pixel_positive_fraction=float(positive[edge].sum()/mass),
            positive_light_within_radii={str(r):float(positive[rr<=r].sum()/mass) for r in (2,4,8,16,24,32)}))
    data=Path(os.environ['LS_SAT_DATA']);truth=data/'image-v14_repeat/v14_south_response_1/trial02/truth.npy'
    t=np.load(truth,allow_pickle=False)
    write_json(Path('results/v14/ps1_ipp/blank_pilot/kernel_audit.json'),dict(job=os.environ['SLURM_JOB_ID'],
        stack_proof_sha256=sha(source),rows=rows,original_physical_truth_sha256=sha(truth),
        original_truth_rows=len(t),original_truth_columns=list(t.dtype.names),
        official_source_basis='psModules/src/objects/pmPSF_IO.c: centre-of-field unit-peak 65x65 PSF_MODEL representation, not an arbitrary local PSF or a documented total-flux-normalized injection kernel.',
        physical_PS1_response_validated=False,pixel_injection_performed=False,
        scope='Inspect real fitted kernels and existing shared-star schema only. Finite support, field dependence, stack calibration and source-photon noise remain requirements before physical-response use. Do not treat coadd data units as individual photon counts.'))
    print('Audited five actual native PSF representations; no injection or response claimed.')


if __name__=='__main__':main()
