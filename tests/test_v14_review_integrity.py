import unittest

import numpy as np

from scripts.v14_review_integrity import verify


class SavedMembershipTest(unittest.TestCase):
    def test_stale_probabilities_fail_likelihood_even_with_same_count_and_sum(self):
        ids=np.array([(1,2,3),(1,2,4)])
        p=np.array([.2,.8]);norm=p.sum()
        row=dict(n_local=2,richness=2,profile_integral=.5,
                 ts=2*(-np.log1p(-p).sum()-norm))
        self.assertTrue(verify(row,ids,p)['verified'])
        with self.assertRaisesRegex(ValueError,'likelihood'):
            verify(row,ids,np.array([.5,.5]))

    def test_zero_richness_and_duplicate_identity(self):
        row=dict(n_local=2,richness=0,profile_integral=.8,ts=0)
        self.assertTrue(verify(row,np.array([(1,2,3),(1,2,4)]),np.zeros(2))['verified'])
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            verify(row,np.array([(1,2,3),(1,2,3)]),np.zeros(2))
