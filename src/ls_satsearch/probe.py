"""Small real DR11 coverage and schema probe on a Slurm compute node."""
import json
import os
from pathlib import Path

import fitsio
import numpy as np
import yaml

from .data import Field, load_bricks, make_area, select, sweeps


def main():
    root = Path(os.environ['LS_DR11_ROOT'])
    config = yaml.safe_load(Path('configs/search.yaml').read_text())
    data_path = Path(os.environ['LS_SAT_DATA'])
    with fitsio.FITS(data_path / 'resources/census.fits.gz') as f:
        print('Census HDUs:', f, flush=True)
        print({k: v for k, v in dict(f[1].read_header()).items()
               if k in ('NSIDE', 'ORDERING', 'NAXIS2', 'TFORM1', 'TTYPE1', 'INDXSCHM')}, flush=True)
    bricks = load_bricks(root)
    print('Brick summary columns:', bricks.dtype.names, flush=True)
    field = Field(210.020, 14.5135, 0.25, 1/6, buffer=0)
    data, provenance = sweeps(root, field)
    coverage, info = make_area(root, field, bricks, sum(1 << b for b in config['reject_maskbits']), 2)
    _, cutflow, _, _, _ = select(data, field, coverage, config)
    result = {'job': os.environ.get('SLURM_JOB_ID'), 'provenance': provenance,
              'coverage_fraction': float(np.mean(coverage)), 'cutflow': cutflow, **info}
    out = Path('results/summary') / 'bootes_schema_probe.json'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print('Boötes core coverage and selected count:', result['coverage_fraction'], cutflow['psf'], flush=True)


if __name__ == '__main__':
    main()
