"""Compare actual PS1 catalogue PSF/noise conditions without transporting a selection model."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np
import yaml

from ls_satsearch.matched import reddening
from ls_satsearch.run import read_csv,sha,write_csv,write_json

CONFIG=Path('configs/v14_repeat/ps1_conditions.yaml')
OUT=Path('results/v14/repeat_full/ps1_observing_conditions')
COLUMNS=['objID','raStack','decStack','primaryDetection','iPSFMag','iKronMag']
for band in 'gri':COLUMNS.extend([band+'PSFMag',band+'PSFFlux',band+'PSFFluxErr',band+'psfMajorFWHM',band+'psfMinorFWHM',band+'psfQfPerfect',band+'expTime'])
COLUMNS=list(dict.fromkeys(COLUMNS))


def quantile(values):return np.quantile(values,[.16,.5,.84]).tolist() if len(values) else [None]*3


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Acquire/read source catalogues on a compute node')
    spec=yaml.safe_load(CONFIG.read_text());checksum=sha(CONFIG)
    sites=read_csv(Path(spec['source_fields']));sites.append(spec['cosmos_local_control'])
    folder=Path(os.environ['LS_SAT_DATA'])/'resources/v14/ps1_conditions'/checksum[:16];folder.mkdir(parents=True,exist_ok=True)
    with urlopen(spec['api']+'/metadata',timeout=60) as r:body=r.read(2000001)
    if len(body)>2000000:raise ValueError('PS1 column metadata exceeded bound')
    metadata=json.loads(body);names={r['name'].lower() for r in metadata}
    if not all(k.lower() in names for k in COLUMNS):raise ValueError('Requested PS1 conditions schema changed')
    metapath=folder/'metadata.json';metapath.write_bytes(body)
    def acquire(site):
        ident=site['field'];rows=[];seen=set();pages=[];duplicate_rows=0
        for page in range(1,11):
            params=dict(ra=float(site['ra_deg']),dec=float(site['dec_deg']),radius=spec['cone_radius_deg'],primaryDetection=1,pagesize=25000,page=page,sort_by='[objID]',columns='['+','.join(COLUMNS)+']')
            url=spec['api']+'.csv?'+urlencode(params);path=folder/f'{ident}-{page:02d}.csv'
            if not path.exists():
                with urlopen(url,timeout=120) as r:body=r.read(30000001)
                if len(body)>30000000:raise ValueError('PS1 conditions page exceeded bound')
                pending=path.with_suffix('.partial');pending.write_bytes(body);pending.replace(path)
            text=path.read_text(encoding='utf-8-sig');reader=csv.DictReader(io.StringIO(text));mapping={k.lower():k for k in reader.fieldnames or ()}
            if not all(k.lower() in mapping for k in COLUMNS):raise ValueError('Unexpected PS1 conditions response header')
            records=list(reader)
            for record in records:
                row={key:record[mapping[key.lower()]] for key in COLUMNS}
                if row['primaryDetection'] not in ('1','true','True'):raise ValueError('Non-primary row returned')
                if row['objID'] in seen:
                    duplicate_rows+=1
                    continue
                seen.add(row['objID']);rows.append(row)
            pages.append(dict(path=str(path),sha256=sha(path),url=url,rows=len(records)))
            if len(records)<25000:break
        else:raise ValueError('PS1 conditions query reached explicit paging cap')
        return site,rows,pages,duplicate_rows
    reports=[];output=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(acquire,s):s for s in sites}
        for future in as_completed(futures):
            site=futures[future]
            try:site,rows,pages,duplicate_rows=future.result()
            except Exception as exc:
                reports.append(dict(site=site['field'],state='failed',error=f'{type(exc).__name__}: {exc}'));continue
            arr={key:np.array([float(r[key] or 'nan') for r in rows]) for key in COLUMNS if key not in ('objID','primaryDetection')}
            finite=np.isfinite(arr['raStack'])&np.isfinite(arr['decStack'])&(arr['raStack']>=0)&(arr['raStack']<360)&(abs(arr['decStack'])<=90)
            invalid_positions=int((~finite).sum());arr={key:values[finite] for key,values in arr.items()};nvalid=int(finite.sum())
            if not nvalid:
                reports.append(dict(site=site['field'],state='no_valid_stack_positions',invalid_stack_positions=invalid_positions,pages=pages));continue
            sky=SkyCoord(arr['raStack'],arr['decStack'],unit='deg');center=SkyCoord(float(site['ra_deg']),float(site['dec_deg']),unit='deg');radius=sky.separation(center).arcmin
            ebv=reddening(arr['raStack'],arr['decStack']);point=(arr['iPSFMag']>0)&(arr['iPSFMag']<22)&(arr['iKronMag']>0)&(arr['iPSFMag']-arr['iKronMag']<.05)
            unit_checks={}
            for band,extinction in zip('gri',[3.172,2.271,1.682]):
                mag=arr[band+'PSFMag'];flux=arr[band+'PSFFlux'];error=arr[band+'PSFFluxErr'];major=arr[band+'psfMajorFWHM'];minor=arr[band+'psfMinorFWHM'];qf=arr[band+'psfQfPerfect']
                valid=np.isfinite(mag+flux+error+major+minor+qf)&(mag>0)&(mag<40)&(flux>0)&(error>0)&(major>0)&(minor>0)&(qf>=.95)&(qf<=1.01)
                snr=np.divide(flux,error,out=np.full(nvalid,np.nan),where=error>0)
                check=valid&(snr>10)
                offsets=mag[check]+2.5*np.log10(flux[check]/3631.)
                unit_checks[band]=dict(n=int(check.sum()),median_mag_minus_flux_AB=float(np.median(offsets)) if len(offsets) else None)
                if len(offsets)>=20 and abs(np.median(offsets))>.02:raise ValueError('PS1 Jy/magnitude relation inconsistent with official units')
                fwhm=np.sqrt(np.maximum(major*minor,0))
                depth=np.full(nvalid,np.nan);positive=np.isfinite(error)&(error>0);depth[positive]=-2.5*np.log10(5*error[positive]/3631.)
                snr=np.divide(flux,error,out=np.full(nvalid,np.nan),where=error>0)
                for region in spec['radial_strata_arcmin']:
                    area=(radius>=region[0])&(radius<region[1])
                    for label,selection in [('all_primary',np.ones(nvalid,bool)),('bright_i_point_proxy',point)]:
                        for low,high in zip(spec['magnitude_edges'],spec['magnitude_edges'][1:]):
                            use=valid&area&selection&(mag>=low)&(mag<high)
                            noise=use&(snr>=spec['formal_noise_SNR_range'][0])&(snr<=spec['formal_noise_SNR_range'][1])
                            fq=quantile(fwhm[use]);dq=quantile(depth[noise]);eq=quantile((depth-extinction*ebv)[noise]);tq=quantile(arr[band+'expTime'][use])
                            output.append(dict(site=site['field'],band=band,radial_low_arcmin=region[0],radial_high_arcmin=region[1],sample=label,observed_mag_low=low,observed_mag_high=high,sources=int(use.sum()),noise_sources=int(noise.sum()),condition_count_supported=int(use.sum())>=spec['minimum_sources'],formal_noise_count_supported=int(noise.sum())>=spec['minimum_sources'],PSF_FWHM_arcsec_p16=fq[0],PSF_FWHM_arcsec_median=fq[1],PSF_FWHM_arcsec_p84=fq[2],formal_observed_m5_p16=dq[0],formal_observed_m5_median=dq[1],formal_observed_m5_p84=dq[2],formal_dereddened_m5_p16=eq[0],formal_dereddened_m5_median=eq[1],formal_dereddened_m5_p84=eq[2],exposure_seconds_median=tq[1]))
            reports.append(dict(site=site['field'],state='acquired_and_measured',unique_primary_sources=len(rows),primary_sources=nvalid,invalid_stack_positions=invalid_positions,discarded_split_primary_rows=duplicate_rows,pages=pages,unit_checks=unit_checks))
            print('PS1_CONDITIONS',site['field'],len(rows),flush=True)
    OUT.mkdir(parents=True,exist_ok=True);write_csv(OUT/'source_sampled_conditions.csv',output)
    if sha(CONFIG)!=checksum:raise ValueError('Conditions protocol changed during measurement')
    write_json(OUT/'manifest.json',dict(job=os.environ['SLURM_JOB_ID'],utc=datetime.now(timezone.utc).isoformat(),config_sha256=checksum,source_fields_sha256=sha(Path(spec['source_fields'])),code_sha256=sha(Path(__file__)),metadata=dict(path=str(metapath),sha256=sha(metapath),selected=[r for r in metadata if r['name'].lower() in {c.lower() for c in COLUMNS}]),fields=reports,physical_PS1_transfer_validated=False,scope=spec['scope']+' FWHM is already in arcsec; do not multiply by plate scale. Flux/error are Jy and the3631Jy AB relation is checked against actual PSF magnitudes. No area is estimated from the number of detections. Multiple primary rows are documented split stack detections; retain the first objID row as in the unchanged canonical PS1 reader, count discarded rows, and do not use the documented corrupted DR2 bestDetection flag.'))
    if any(r['state']!='acquired_and_measured' for r in reports):
        raise RuntimeError('PS1 conditions acquisition incomplete; inspect the saved manifest')


if __name__=='__main__':run()
