"""Image-bound five-band blank photometry/quality comparison, not stellar truth."""
import csv
import json
import os
from pathlib import Path
import numpy as np
from astropy.io import fits
from scipy.spatial import cKDTree
from ls_satsearch.expansion import unit
from ls_satsearch.run import sha,write_csv,write_json
from scripts.v14_ps1_operator_compare import quantiles


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Native stack comparison requires Slurm')
    base=Path('results/v14/ps1_ipp/blank_pilot')
    proof=base/'stack_preflight_61622347.json';m=json.loads(proof.read_text())
    if m['returncode']!=0:raise ValueError('Native stack did not complete')
    acquisition=base/'acquisition.json';a=json.loads(acquisition.read_text())
    refs=[]
    for p in a['reference_pages']:
        if sha(Path(p['path']))!=p['sha256']:raise ValueError('Reference changed')
        with Path(p['path']).open() as f:refs.extend(csv.DictReader(f))
    get=lambda k:np.array([float(r[k]) for r in refs])
    ra,dec=get('raStack'),get('decStack')
    sky=np.isfinite(ra+dec)&(ra>=0)&(ra<360)&(abs(dec)<=90)
    rows,summaries,native_map=[],{},{}
    aligned={}
    for band in 'grizy':
        image=m['image_ids_from_same_cell_DR2'][band]
        path=Path(m['raw_output_root'])/f'native_grizy.stk.{image}.cmf'
        if sha(path)!=m['artifacts'][path.name]['sha256']:raise ValueError('Native source output changed')
        with fits.open(path) as hd:
            hdu=next(h for h in hd if {'RA_PSF','DEC_PSF','CAL_PSF_MAG','PSF_INST_FLUX'} <= set(getattr(getattr(h,'columns',None),'names',[]) or []))
            table=hdu.data.copy();header=hd[0].header
            psf={k:header.get(k) for k in ('PSF_OK','NPSFSTAR','PSFMODEL','FPA.ZP','EXPTIME')}
        nr,nd=table['RA_PSF'],table['DEC_PSF']
        nv=np.isfinite(nr+nd)&(nr>=0)&(nr<360)&(abs(nd)<=90)
        ni=np.flatnonzero(nv)
        use=sky&np.array([int(r[band+'stackImageID'])==image for r in refs])
        ri=np.flatnonzero(use)
        npnt,rpnt=unit(nr[ni],nd[ni]),unit(ra[ri],dec[ri])
        d,j=cKDTree(npnt).query(rpnt);back=cKDTree(rpnt).query(npnt)[1]
        sep=2*np.rad2deg(np.arcsin(np.clip(d/2,0,1)))*3600
        ok=(back[j]==np.arange(len(ri)))&(sep<=.8)
        indices=np.full(len(refs),-1,dtype=int);indices[ri[ok]]=ni[j[ok]]
        detected=indices>=0
        rm=get(band+'PSFMag');rf=get(band+'PSFFlux');re=get(band+'PSFFluxErr')
        ref_good=use&np.isfinite(rm+rf+re)&(rm>0)&(rm<35)&(rf>0)&(re>0)
        native_mag=np.full(len(refs),np.nan);native_snr=np.zeros(len(refs))
        native_mag[detected]=table['CAL_PSF_MAG'][indices[detected]]
        flux=table['PSF_INST_FLUX'];error=table['PSF_INST_FLUX_SIG']
        native_snr[detected]=np.divide(flux[indices[detected]],error[indices[detected]],
                                       out=np.zeros(detected.sum()),where=error[indices[detected]]>0)
        native_mag[~((native_mag>0)&(native_mag<35))]=np.nan
        aligned[band]=dict(indices=indices,reference_valid=ref_good,native_mag=native_mag,native_snr=native_snr,
                           reference_snr=np.divide(rf,re,out=np.zeros_like(rf),where=re>0),detected=detected)
        native_map[band]=table
        for lo,hi in zip([17,20,21,22,23,24],[20,21,22,23,24,25.5]):
            selected=ref_good&(rm>=lo)&(rm<hi);both=selected&detected
            q=quantiles(native_mag[both]-rm[both])
            rows.append(dict(band=band,reference_g_min=None,mag_min=lo,mag_max=hi,
                exact_image_reference_rows=int(selected.sum()),mutual_matches=int(both.sum()),
                reference_snr5=int((selected&(aligned[band]['reference_snr']>=5)).sum()),
                native_snr5_in_reference_rows=int((selected&(native_snr>=5)).sum()),
                **{'native_minus_DR2_mag_'+k:v for k,v in q.items()}))
        summaries[band]=dict(native_rows=len(table),exact_image_reference_rows=int(use.sum()),
            mutual_matches=int(detected.sum()),native_ids_unique=len(set(table['IPP_IDET']))==len(table),
            PSF=psf,separation_arcsec=quantiles(sep[ok]),
            calibrated_mag_residual=quantiles(native_mag[ref_good]-rm[ref_good]),
            qf_residual=quantiles(table['PSF_QF_PERFECT'][indices[detected]]-get(band+'psfQfPerfect')[detected]))
    paired=np.logical_and.reduce([aligned[b]['reference_valid']&aligned[b]['detected'] for b in 'gri'])
    ref_quality=paired&np.logical_and.reduce([aligned[b]['reference_snr']>=5 for b in 'gri'])
    native_quality=paired&np.logical_and.reduce([(aligned[b]['native_snr']>=5)&np.isfinite(aligned[b]['native_mag']) for b in 'gri'])
    i=native_map['i'];ii=aligned['i']['indices'];native_morph=np.full(len(refs),np.nan)
    found=ii>=0;f=i['PSF_INST_FLUX'][ii[found]];k=i['KRON_FLUX'][ii[found]]
    native_morph[found]=np.where((f>0)&(k>0),-2.5*np.log10(np.maximum(f,1e-30)/np.maximum(k,1e-30)),np.nan)
    ref_morph=get('iPSFMag')-get('iKronMag')
    ref_point=ref_quality&(get('iKronMag')>0)&(ref_morph<.05)
    native_point=native_quality&(native_morph<.05)
    eligible=ref_quality|native_quality
    identity_agree=np.zeros(len(refs),dtype=bool)
    for n in np.flatnonzero(paired):
        identity_agree[n]=len({int(native_map[b]['IPP_IDET'][aligned[b]['indices'][n]]) for b in 'gri'})==1
    out=base/'stack_comparison';out.mkdir(exist_ok=True)
    write_csv(out/'by_band_magnitude.csv',rows)
    write_json(out/'summary.json',dict(job=os.environ['SLURM_JOB_ID'],inputs={str(p):sha(p) for p in (proof,acquisition)},
        runner_sha256=sha(Path(__file__)),bands=summaries,reference_rows=len(refs),
        unique_reference_objects=len({r['objID'] for r in refs}),matched_gri_reference_rows=int(paired.sum()),
        matched_gri_same_native_ID=int(identity_agree.sum()),gri_snr5_reference=int(ref_quality.sum()),
        gri_snr5_native_on_matched_refs=int(native_quality.sum()),
        point_proxy_contingency=dict(both=int((ref_point&native_point).sum()),reference_only=int((ref_point&~native_point).sum()),
                                     native_only=int((native_point&~ref_point).sum()),neither=int((eligible&~ref_point&~native_point).sum())),
        i_psf_minus_kron_residual=quantiles(native_morph[ref_quality&native_quality]-ref_morph[ref_quality&native_quality]),
        DR2_operator_equivalence_validated=False,physical_PS1_response_validated=False,
        scope='Descriptive five-band blank comparison restricted per band to actual FITS STK_ID, mutual nearest 0.8arcsec, no fitted coordinate/magnitude shift. '
              'SNR5 and iPSF-iKron<0.05 compare measurements only among matched exact-image references; no stellar truth, primary/footprint/extinction/magnitude final sample or physical completeness. '
              'All native-only sources, faint-blue morphology/selection, other skies and uncertainty still require assessment before physical response.'))
    print(json.dumps(dict(job=os.environ['SLURM_JOB_ID'],native_counts={b:s['native_rows'] for b,s in summaries.items()},paired_gri=int(paired.sum()))))


if __name__=='__main__':main()
