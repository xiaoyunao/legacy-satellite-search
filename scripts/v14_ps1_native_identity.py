"""Native PS1 header/image-ID provenance audit; never emit source rows."""
from collections import Counter
import csv
import json
import os
from pathlib import Path
from astropy.io import fits
from ls_satsearch.run import sha, write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Native PS1 audit requires Slurm')
    source = Path('results/v14/ps1_ipp/blank_pilot/acquisition.json')
    a = json.loads(source.read_text())
    refs = []
    for p in a['reference_pages']:
        if sha(Path(p['path'])) != p['sha256']:
            raise ValueError('Reference bytes changed')
        with Path(p['path']).open() as stream:
            refs.extend(csv.DictReader(stream))
    rows = []
    for p in a['products']:
        if p['type'] != 'stack':
            continue
        if sha(Path(p['path'])) != p['sha256']:
            raise ValueError('Native image changed')
        with fits.open(p['path']) as hd:
            headers = [{k: h.header[k] for k in h.header if any(s in k for s in
                       ('STK', 'STACK', 'CELL', 'TESS', 'VERSION', 'IPP', 'FPA.EXP', 'FPA.ZP', 'FPA.FILTER'))}
                       for h in hd]
        rows.append(dict(band=p['filter'], image_path=p['path'], headers=headers,
                    DR2_image_id_counts=dict(Counter(r[p['filter']+'stackImageID'] for r in refs))))
    write_json(Path('results/v14/ps1_ipp/blank_pilot/native_identity.json'),dict(
        job=os.environ['SLURM_JOB_ID'], acquisition_sha256=sha(source), rows=rows,
        physical_PS1_response_validated=False,
        scope='Same skycell can have multiple DR2 image IDs; native image identity must be audited before binding the stack operator or claiming DR2 equivalence.'))
    print('Inspected five native science headers and reference image-ID counts.')


if __name__ == '__main__':
    main()
