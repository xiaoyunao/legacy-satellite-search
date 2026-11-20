"""Inspect native operator products on allocated CPU; emit schemas, not source rows."""
import json
import os
from pathlib import Path
from astropy.io import fits
from ls_satsearch.run import sha, write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Native FITS inspection requires Slurm')
    proof = Path('results/v14/ps1_ipp/blank_pilot/preflight_61621698.json')
    m = json.loads(proof.read_text())
    if m['returncode'] != 0:
        raise ValueError('Native operator did not complete')
    root = Path(m['raw_output_root'])
    records = []
    for name, item in m['artifacts'].items():
        if not name.endswith(('.cmf', '.psf')):
            continue
        path = root / name
        if sha(path) != item['sha256']:
            raise ValueError('Native output changed')
        with fits.open(path) as hd:
            for i, h in enumerate(hd):
                cols = getattr(h, 'columns', None)
                records.append(dict(file=name, hdu=i, name=h.name,
                    rows=h.header.get('NAXIS2'),
                    columns=[dict(name=c.name, format=c.format, unit=c.unit) for c in cols] if cols else [],
                    header={k: h.header[k] for k in h.header if
                            any(token in k for token in ('ZP', 'MAG', 'PSF', 'FPA', 'EXPTIME', 'WCS'))}))
    write_json(Path('results/v14/ps1_ipp/blank_pilot/native_schema.json'),dict(
        job=os.environ['SLURM_JOB_ID'], preflight_sha256=sha(proof), schema=records,
        physical_PS1_response_validated=False))
    print('Inspected', len(records), 'native HDUs; no source rows exported.')


if __name__ == '__main__':
    main()
