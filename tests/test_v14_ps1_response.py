import unittest
import numpy as np
from scripts.v14_ps1_response import stage_masks


class PS1StageTest(unittest.TestCase):
    def test_i_and_morphology_are_real_nested_selection_stages(self):
        rows=np.array([[1,2,22,21.5,.03,.03,21.3,21.3,.03],
                       [1,2,22,21.5,.03,.03,-999,21.3,.03],
                       [1,2,22,21.5,.03,.03,21.3,21.1,.03],
                       [1,2,22,21.5,.5,.03,21.3,21.3,.03]])
        m=stage_masks(rows,np.zeros(4),dict(min_snr=5,g_max=24,r_max=23.5))
        self.assertEqual(m['gr'].tolist(),[True,True,True,False])
        self.assertEqual(m['i_valid'].tolist(),[True,False,True,False])
        self.assertEqual(m['selected'].tolist(),[True,False,False,False])
        chain=[m[k] for k in ('gr','i_valid','i_snr','morphology','selected')]
        self.assertTrue(all(np.all(b<=a) for a,b in zip(chain,chain[1:])))
