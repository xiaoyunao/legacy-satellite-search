"""Record the actual CCD inputs used in the native blank and injection runs."""
import os
from pathlib import Path

import fitsio

from ls_satsearch.run import read_csv, settings, sha, write_csv, write_json


if __name__ == '__main__':
    _, data, _ = settings()
    rows, inputs = [], {}
    for site in read_csv(Path('configs/v13/image_fields.csv')):
        field = site['field']
        for folder in sorted((data/'image-v13'/field).iterdir()):
            if folder.name!='blank' and not folder.name.startswith('trial'):
                continue
            path, = folder.glob('coadd/*/*/*-ccds.fits')
            arr=fitsio.read(path,upper=True)
            columns=('EXPNUM','CCDNAME','FILTER','IMAGE_FILENAME','IMAGE_HDU','PLVER')
            identities=[tuple(str(value).strip() for value in t) for t in arr[list(columns)]]
            if folder.name=='blank':
                blank=set(identities)
                for ident in identities:
                    rows.append(dict(site=field,**dict(zip((k.lower() for k in columns),ident))))
            if blank != set(identities):
                raise ValueError(f'Input CCDs changed from blank to {field}/{folder.name}')
            inputs[f'{field}/{folder.name}']=dict(n=len(arr),sha256=sha(path))
    output=Path('results/v13/image_response')
    output.mkdir(exist_ok=True, parents=True)
    write_csv(output/'ccd_inputs.csv',rows)
    write_json(output/'ccd_inputs.json',dict(job=os.getenv('SLURM_JOB_ID'),container=
               'docker:legacysurvey/legacypipe:DR11.1.0',image_digest=
               '5d32c09932',inputs=inputs))
