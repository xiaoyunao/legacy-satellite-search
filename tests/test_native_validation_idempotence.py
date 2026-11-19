import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitsio
import numpy as np

from scripts.v14_repeat import validate


class NativeValidationIdentityTest(unittest.TestCase):
    def test_recheck_preserves_original_proof_and_rejects_changed_truth(self):
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';trial=data/'image-v14_repeat/f/trial00'
            (trial/'tractor/a').mkdir(parents=True)
            fields=('RA','DEC','TYPE','FLUX_G','FLUX_R','FLUX_IVAR_G','FLUX_IVAR_R')
            table=np.zeros(1,dtype=[(k,'S3' if k=='TYPE' else 'f8') for k in fields])
            fitsio.write(trial/'tractor/a/tractor-a.fits',table)
            for name,array in [('truth',np.array([1.])),('injected_exposures',np.ones((1,4))),('initial_detection',np.zeros((1,2)))]:
                np.save(trial/(name+'.npy'),array,allow_pickle=False)
            (trial/'truth.json').write_text(json.dumps(dict(shared_population_rows_verified=True,source_poisson_seed=1)))
            try:
                os.chdir(root)
                with patch.dict(os.environ,LS_SAT_DATA=str(data),SLURM_JOB_ID='123'):
                    validate('f','trial00')
                    proof=Path('results/v14/repeat/validation/f-trial00.json');original=proof.read_bytes()
                    with patch.dict(os.environ,SLURM_JOB_ID='456'):validate('f','trial00')
                    self.assertEqual(proof.read_bytes(),original)
                    np.save(trial/'truth.npy',np.array([2.]),allow_pickle=False)
                    with self.assertRaises(ValueError):validate('f','trial00')
                    self.assertEqual(proof.read_bytes(),original)
            finally:os.chdir(previous)


if __name__=='__main__':unittest.main()
