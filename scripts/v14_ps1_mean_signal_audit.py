"""Diagnose a failed bright-unit preflight without rerunning or tuning psphot."""
import json
import os
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import sha, write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Actual image/catalogue audit requires Slurm')
    base=Path('results/v14/ps1_ipp/blank_pilot')
    proof=base/'mean_signal_probe_61625458.json'
    m=json.loads(proof.read_text())
    blank=json.loads((base/'stack_preflight_61622347.json').read_text())
    acquisition=json.loads((base/'acquisition.json').read_text())
    products={(p['filter'],p['type']):p for p in acquisition['products']}
    folder=Path(m['generated_images'][0]['path']).parent
    truth=np.load(folder/'truth.npy',allow_pickle=False)
    if sha(folder/'truth.npy')!=m['source_truth_sha256']:
        raise ValueError('Original calibration positions/magnitudes changed')
    rows=[]
    for b,band in enumerate('grizy'):
        generated=m['generated_images'][b]
        if sha(Path(generated['path']))!=generated['sha256']:
            raise ValueError('Generated linear pixels changed')
        with fits.open(generated['path'],memmap=False) as hd:
            h=next(h for h in hd if h.header.get('NAXIS')==2)
            image=h.data.astype(float);header=h.header.copy()
        source=Path(products[band,'stack']['path'])
        if sha(source)!=generated['input_sha256']:
            raise ValueError('Original native pixels changed')
        with fits.open(source,memmap=False) as hd:
            h=next(h for h in hd if h.header.get('NAXIS')==2)
            original=2*float(h.header['BSOFTEN'])*np.sinh(h.data.astype(float)/1.0857362)+float(h.header['BOFFSET'])
        w=WCS(header);expected=10**(.4*(float(header['FPA.ZP'])+2.5*np.log10(float(header['EXPTIME']))-truth[:,4+b]))
        ratios=[]
        for (x,y),flux in zip(truth[:,2:4].astype(int),expected):
            ratios.append(float((image[y-32:y+33,x-32:x+33]-original[y-32:y+33,x-32:x+33]).sum()/flux))
        image_id=blank['image_ids_from_same_cell_DR2'][band]
        path=folder/f'probe.stk.{image_id}.cmf'
        with fits.open(path) as hd:
            table=next(h.data.copy() for h in hd if 'RA_PSF' in (getattr(getattr(h,'columns',None),'names',[]) or []))
            meta=hd[0].header.copy()
        valid=np.isfinite(table['RA_PSF']+table['DEC_PSF'])&(abs(table['DEC_PSF'])<=90)
        indices=np.flatnonzero(valid)
        _,near=cKDTree(unit(table['RA_PSF'][indices],table['DEC_PSF'][indices])).query(unit(truth[:1,0],truth[:1,1]))
        r=table[indices[near[0]]]
        x,y=w.world_to_pixel_values(float(r['RA_PSF']),float(r['DEC_PSF']))
        get=lambda k:float(r[k]) if k in table.dtype.names and np.isfinite(r[k]) else None
        rows.append(dict(band=band,calibrators=len(truth),
            finite_patch_added_flux_ratio_min=min(ratios),finite_patch_added_flux_ratio_max=max(ratios),
            bright_world_centroid_dx_pixels=float(x-truth[0,2]),bright_world_centroid_dy_pixels=float(y-truth[0,3]),
            bright_instrumental_PSF_flux_over_added_flux=get('PSF_INST_FLUX')/expected[0],
            bright_calibrated_minus_input_mag=get('CAL_PSF_MAG')-float(truth[0,4+b]),
            bright_aperture_mag=get('AP_MAG'),bright_raw_aperture_mag=get('AP_MAG_RAW'),
            bright_PSF_instrumental_mag=get('PSF_INST_MAG'),bright_flags=int(r['FLAGS']),bright_flags2=int(r['FLAGS2']),
            PSF_aperture_residual_header=meta.get('PSPHOT.PSF.APRESID')))
    write_json(base/'mean_signal_diagnostic.json',dict(job=os.environ['SLURM_JOB_ID'],
        input_sha256={str(proof):sha(proof)},runner_sha256=sha(Path(__file__)),rows=rows,
        operator_refitted=False,unit_check_passed=False,physical_PS1_response_validated=False,Pdet_measured=False,
        scope='Read-only pixel-flux and bright measurement diagnosis after the registered unit check failed. Finite normalized PSF-model images and global astrometry/aperture calibration are not validated local stellar injection models; no fitted magnitude correction, retuned detector or new system trial.'))


if __name__=='__main__':main()
