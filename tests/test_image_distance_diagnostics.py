import unittest
from unittest.mock import patch

from scripts.v13_image_trials import blind


class ImageDistanceDiagnosticTest(unittest.TestCase):
    def test_other_spatial_group_is_diagnostic_without_changing_registered_best_group(self):
        truth=dict(D_kpc=100,ra_deg=10,dec_deg=20,theta_h_arcmin=.5)
        cfg=dict(match_min_arcmin=2,match_rh_factor=1,match_dm_tolerance=.75)
        a=dict(ranking=10,channel='A_base',ra_deg=10,dec_deg=20,dm=19)
        b=dict(a,ranking=9,dm=20)
        with patch('scripts.v13_image_trials.scan',return_value=([],[],{},object())), \
             patch('scripts.v13_image_trials.groups',return_value=[(a,[a]),(b,[b])]):
            result=blind(None,None,None,None,cfg,truth,5,diagnostics=True)
        self.assertTrue(result['spatial'])
        self.assertEqual(result['blind_dm'],19)
        self.assertFalse(result['correct_mode_exists'])
        self.assertTrue(result['correct_mode_in_any_spatial_group'])
        self.assertEqual(result['n_spatial_matching_groups'],2)


if __name__=='__main__':unittest.main()
