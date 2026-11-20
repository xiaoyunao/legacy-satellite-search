"""Real-stack mean-signal unit/source-response preflight; never physical Pdet."""
import json
import os
from pathlib import Path
import subprocess
import time
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.spatial import cKDTree
import yaml
from ls_satsearch.expansion import unit
from ls_satsearch.run import sha,write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Native PS1 pixel processing requires Slurm')
    config=Path('configs/v14_ps1_operator/mean_signal_probe.yaml');spec=yaml.safe_load(config.read_text())
    base=Path('results/v14/ps1_ipp/blank_pilot');proof=base/'stack_preflight_61622347.json'
    m=json.loads(proof.read_text());a=json.loads((base/'acquisition.json').read_text())
    data=Path(os.environ['LS_SAT_DATA']);folder=data/'resources/v14/ps1_operator/mean_signal'/os.environ['SLURM_JOB_ID']
    folder.mkdir(parents=True,exist_ok=False)
    template=data/'resources'/spec['template']
    with template.open() as f:header=next(s[1:].split() for s in f if s.startswith('#') and 'M_ini' in s and 'int_IMF' in s)
    cols=[header.index(b+'P1') for b in 'grizy'];values=np.loadtxt(template,usecols=cols)
    phase=np.loadtxt(template,usecols=header.index('stage' if 'stage' in header else 'label'))
    allowed=(phase==1)&(values[:,0]-values[:,1]>=0)&(values[:,0]-values[:,1]<=.4)
    choices=np.flatnonzero(allowed)
    row=choices[np.argmin((values[choices,0]-4.)**2)]
    magnitudes=np.asarray(spec['observed_pixel_frame_g'])[:,None]+values[row]-values[row,0]
    products={(p['filter'],p['type']):p for p in a['products']}
    raw=products['g','stack']
    with fits.open(raw['path'],memmap=False) as hd:
        h=next(h for h in hd if h.header.get('NAXIS')==2);reference_header=h.header.copy()
        wcs=WCS(reference_header);shape=h.shape
    scale=np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix)))*3600
    cx,cy=wcs.world_to_pixel_values(float(a['site']['ra_deg']),float(a['site']['dec_deg']))
    rng=np.random.default_rng(spec['seed']);positions=[]
    mask_files=[fits.open(products[b,'stack.mask']['path'],memmap=False) for b in 'grizy']
    try:
        for _ in range(10000):
            radius=np.sqrt(rng.random())*spec['placement_radius_arcsec']/scale;angle=rng.uniform(0,2*np.pi)
            x,y=int(round(cx+radius*np.cos(angle))),int(round(cy+radius*np.sin(angle)))
            if not 34<=x<shape[1]-34 or not 34<=y<shape[0]-34:continue
            if any(np.hypot(x-px,y-py)*scale<spec['minimum_separation_arcsec'] for px,py in positions):continue
            # Clean central pixels are a declared software-preflight condition,
            # not a survey mask definition or an all-sky selection function.
            if any(int(next(h for h in hd if h.header.get('NAXIS')==2).section[y:y+1,x:x+1][0,0])!=0 for hd in mask_files):continue
            positions.append((x,y))
            if len(positions)==len(magnitudes):break
    finally:
        for hd in mask_files:hd.close()
    if len(positions)!=len(magnitudes):raise ValueError('No registered clean separated preflight positions')
    xy=np.asarray(positions);ra,dec=wcs.pixel_to_world_values(xy[:,0],xy[:,1])
    truth=np.column_stack([ra,dec,xy,magnitudes]);np.save(folder/'truth.npy',truth,allow_pickle=False)
    blocks=['INPUT MULTI\n'];generated=[]
    for b,band in enumerate('grizy'):
        p=products[band,'stack'];path=Path(p['path'])
        if sha(path)!=p['sha256']:raise ValueError('Acquired native image changed')
        with fits.open(path,memmap=False) as hd:
            h=next(h for h in hd if h.header.get('NAXIS')==2);header=h.header.copy();primary=hd[0].header.copy()
            bw=WCS(header)
            if not (np.allclose(bw.wcs.crpix,wcs.wcs.crpix,rtol=0,atol=1e-8) and
                    np.allclose(bw.wcs.crval,wcs.wcs.crval,rtol=0,atol=1e-8) and
                    np.allclose(bw.pixel_scale_matrix,wcs.pixel_scale_matrix,rtol=0,atol=1e-12)):
                raise ValueError('Five-band native pixel grids differ; no implicit interpolation')
            encoded=np.asarray(h.data,dtype=float)
            # Exact documented psLib inverse, after FITS BSCALE/BZERO handling.
            image=2*float(header['BSOFTEN'])*np.sinh(encoded/1.0857362)+float(header['BOFFSET'])
        image_id=int(header['STK_ID']);psf=Path(m['raw_output_root'])/f'native_grizy.stk.{image_id}.psf'
        if sha(psf)!=m['artifacts'][psf.name]['sha256']:raise ValueError('Blank PSF changed')
        with fits.open(psf) as hd:kernel=np.squeeze(hd['PSF_MODEL'].data).astype(float)
        if kernel.shape!=(65,65) or not np.isfinite(kernel).all() or (kernel<0).any():
            raise ValueError('Preflight requires the observed positive finite kernel')
        kernel/=kernel.sum()
        zp=float(header['FPA.ZP'])+2.5*np.log10(float(header['EXPTIME']))
        flux=10**(.4*(zp-magnitudes[:,b]))
        for (x,y),f in zip(positions,flux):image[y-32:y+33,x-32:x+33]+=f*kernel
        for key in ('BSOFTEN','BOFFSET','BSCALE','BZERO','BLANK'):
            if key in header:del header[key]
        header['LSINJECT']='MEAN_SIGNAL_PREFLIGHT';header.add_history('Synthetic finite-kernel mean signal; not a survey release image or physical completeness experiment.')
        target=folder/f'calibration-{band}.fits'
        fits.HDUList([fits.PrimaryHDU(header=primary),fits.ImageHDU(image.astype('f4'),header=header)]).writeto(target)
        generated.append(dict(band=band,path=str(target),sha256=sha(target),input_sha256=p['sha256'],PSF_sha256=sha(psf)))
        blocks.append(f'INPUT METADATA\n  STACK_ID S64 {image_id}\n  RAW:IMAGE STR {target}\n'
                      f"  RAW:MASK STR {products[band,'stack.mask']['path']}\n"
                      f"  RAW:VARIANCE STR {products[band,'stack.wt']['path']}\nEND\n")
    inputs=folder/'inputs.mdc';inputs.write_text(''.join(blocks))
    rc=Path(m['raw_output_root'])/'ipprc.config'
    binary=data/'software/ipp/install/lssat.lin64/bin/psphotStack'
    cmd=[str(binary),'-ipprc',str(rc),'-threads','8','-input',str(inputs),str(folder/'probe')]
    start=time.monotonic()
    with (folder/'operator.log').open('w') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1350)
    rows=[]
    if result.returncode==0:
        tpoints=unit(ra,dec)
        for b,band in enumerate('grizy'):
            image_id=m['image_ids_from_same_cell_DR2'][band];path=folder/f'probe.stk.{image_id}.cmf'
            with fits.open(path) as hd:
                t=next(h.data.copy() for h in hd if 'RA_PSF' in (getattr(getattr(h,'columns',None),'names',[]) or []))
            ok=np.isfinite(t['RA_PSF']+t['DEC_PSF'])&(abs(t['DEC_PSF'])<=90)
            idx=np.flatnonzero(ok);dist,near=cKDTree(unit(t['RA_PSF'][idx],t['DEC_PSF'][idx])).query(tpoints)
            sep=2*np.rad2deg(np.arcsin(np.clip(dist/2,0,1)))*3600
            original=Path(m['raw_output_root'])/f'native_grizy.stk.{image_id}.cmf'
            with fits.open(original) as hd:
                blank=next(h.data.copy() for h in hd if 'RA_PSF' in (getattr(getattr(h,'columns',None),'names',[]) or []))
            bv=np.isfinite(blank['RA_PSF']+blank['DEC_PSF'])&(abs(blank['DEC_PSF'])<=90)
            bd=cKDTree(unit(blank['RA_PSF'][bv],blank['DEC_PSF'][bv])).query(tpoints)[0]
            blank_sep=2*np.rad2deg(np.arcsin(np.clip(bd/2,0,1)))*3600
            for j in range(len(truth)):
                found=sep[j]<=spec['matching_radius_arcsec'];k=idx[near[j]]
                rows.append(dict(band=band,target_observed_pixel_frame_g=float(magnitudes[j,0]),matched=bool(found),
                    blank_counterpart_within_match_radius=bool(blank_sep[j]<=spec['matching_radius_arcsec']),
                    separation_arcsec=float(sep[j]) if found else None,
                    native_minus_finite_kernel_mag=float(t['CAL_PSF_MAG'][k]-magnitudes[j,b]) if found and 0<t['CAL_PSF_MAG'][k]<35 else None))
    write_json(Path('results/v14/ps1_ipp/blank_pilot')/f"mean_signal_probe_{os.environ['SLURM_JOB_ID']}.json",dict(
        job=os.environ['SLURM_JOB_ID'],returncode=result.returncode,elapsed_s=time.monotonic()-start,
        config_sha256=sha(config),runner_sha256=sha(Path(__file__)),template_sha256=sha(template),
        source_truth_sha256=sha(folder/'truth.npy'),generated_images=generated,measurements=rows,
        source_photon_noise_added=False,variance_covariance_mask_unchanged=True,
        physical_PS1_response_validated=False,Pdet_measured=False,scope=spec['scope']))
    print(json.dumps(dict(job=os.environ['SLURM_JOB_ID'],returncode=result.returncode,calibrators=len(truth),physical_response=False)))


if __name__=='__main__':main()
