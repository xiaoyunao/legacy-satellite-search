"""Acquire a bounded independent morphology/deep-photometry reference on NERSC."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess

import fitsio
import numpy as np
import yaml

from ls_satsearch.run import sha, write_json

CONFIG=Path('configs/v14_repeat/cosmos_reference.yaml')
OUT=Path('results/v14/repeat_full/cosmos_reference')
REQUIRED=('ID','RA','DEC','HSC_G_MAG','HSC_R_MAG','HSC_I_MAG',
          'HSC_G_FLUX','HSC_G_FLUXERR','HSC_R_FLUX','HSC_R_FLUXERR',
          'HSC_G_VALID','HSC_R_VALID','ACS_MU_CLASS','LP_TYPE','FLAG_HSC','EBV_MW')
OPTIONAL=('ID_ACS','HSC_G_MAGERR','HSC_R_MAGERR','HSC_I_MAGERR',
          'HSC_I_FLUX','HSC_I_FLUXERR','HSC_I_VALID','ACS_F814W_FLUX','ACS_F814W_FLUXERR',
          'ACS_FWHM_WORLD','ACS_A_WORLD','ACS_B_WORLD','ACS_FLAGS','ACS_CLASS_STAR',
          'LP_CHIS','LP_CHIQ','LP_CHI2_BEST','FLAG_UVISTA','FLAG_COMBINED',
          'MODEL_FLAG','SOLUTION_MODEL','VALID_SOURCE','N_GROUP')


def acquire():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Download/decompress/read catalogue on a compute node')
    spec=yaml.safe_load(CONFIG.read_text());OUT.mkdir(parents=True,exist_ok=True)
    folder=Path(os.environ['LS_SAT_DATA'])/'resources/independent/cosmos2020'
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/spec['source_url'].rsplit('/',1)[1]
    if not archive.exists():
        part=archive.with_suffix(archive.suffix+'.part')
        subprocess.run(['curl','--fail','--location','--retry','2','--connect-timeout','20',
            '--max-time','1200','--continue-at','-','--output',str(part),spec['source_url']],check=True)
        if part.stat().st_size!=spec['expected_archive_bytes']:raise ValueError('Archive size differs from official static HEAD')
        part.replace(archive)
    if archive.stat().st_size!=spec['expected_archive_bytes']:raise ValueError('Archive size changed')
    archive_sha=sha(archive)
    unpacked=archive.with_suffix('')
    if not unpacked.exists():
        part=unpacked.with_suffix('.unpack.partial')
        with gzip.open(archive,'rb') as source,part.open('wb') as target:
            shutil.copyfileobj(source,target,length=4*1024*1024)
        part.replace(unpacked)
    try:
        with fitsio.FITS(unpacked) as f:
            hdu=f[1];mapping={name.upper():name for name in hdu.get_colnames()}
            # The Phase3 FITS uses these documented names; IRSA's table service
            # presents the same model/SEP coordinates as ra/dec.
            for canonical,original in (('RA','ALPHA_J2000'),('DEC','DELTA_J2000')):
                if canonical not in mapping and original in mapping:mapping[canonical]=mapping[original]
            missing=sorted(set(REQUIRED)-mapping.keys())
            if missing:raise ValueError('Independent reference schema differs: '+','.join(missing))
            names=[name for name in (*REQUIRED,*OPTIONAL) if name in mapping]
            raw=hdu.read(columns=[mapping[name] for name in names],upper=True)
            table=np.empty(len(raw),dtype=[(name,raw.dtype.fields[mapping[name].upper()][0]) for name in names])
            for name in names:table[name]=raw[mapping[name].upper()]
            n_total=hdu.get_nrows();header=hdu.read_header()
            schema={name:dict(original_name=mapping[name],unit=header.get('TUNIT'+str(hdu.get_colnames().index(mapping[name])+1))) for name in names}
        g=table['HSC_G_MAG'];r=table['HSC_R_MAG'];low,high=spec['extract_observed_HSC_g']
        keep=np.isfinite(g)&np.isfinite(r)&np.isfinite(table['RA'])&np.isfinite(table['DEC'])&(g>=low)&(g<high)
        selected=table[keep]
        subset=folder/'farmer_observed_g17_25p5.npy'
        pending=subset.with_suffix('.pending.npy');np.save(pending,selected,allow_pickle=False);pending.replace(subset)
        write_json(OUT/'acquisition.json',dict(job=os.environ['SLURM_JOB_ID'],utc=datetime.now(timezone.utc).isoformat(),
            config_sha256=sha(CONFIG),code_sha256=sha(Path(__file__)),source_url=spec['source_url'],version=spec['version'],
            archive_path=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=archive_sha,
            gzip_integrity_checked_during_decompression=True,source_rows=n_total,extracted_rows=len(selected),
            subset_path=str(subset),subset_sha256=sha(subset),schema=schema,optional_missing=sorted(set(OPTIONAL)-mapping.keys()),
            morphology_counts=dict(Counter(str(value) for value in selected['ACS_MU_CLASS'])),
            SED_type_counts=dict(Counter(str(value) for value in selected['LP_TYPE'])),
            physical_PS1_transfer_validated=False,scope=spec['scope']))
        print('INDEPENDENT_COSMOS_REFERENCE_ACQUIRED',n_total,len(selected),flush=True)
    finally:
        # The authoritative compressed archive and bounded raw subset stay on scratch.
        # The decompressed full catalogue is only an I/O intermediate.
        if unpacked.exists():unpacked.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('acquire',));p.parse_args();acquire()
