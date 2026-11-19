import tempfile
import unittest
from pathlib import Path

import numpy as np

from ls_satsearch.review import membership_path,save_membership


class MembershipArtifactTest(unittest.TestCase):
    def test_later_same_rank_fit_cannot_overwrite_prior_row_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'runs/v14/field-base/membership-main-A-1.npz'
            a=save_membership(root,legacy,np.array([[1,2,3]]),np.array([.2]))
            b=save_membership(root,legacy,np.array([[4,5,6]]),np.array([.8]))
            self.assertNotEqual(a['membership_data_path'],b['membership_data_path'])
            with np.load(membership_path(root,a,legacy),allow_pickle=False) as first:
                np.testing.assert_array_equal(first['source_ids'],[[1,2,3]])
                np.testing.assert_array_equal(first['probability'],[.2])
            with np.load(legacy,allow_pickle=False) as current:
                np.testing.assert_array_equal(current['probability'],[.8])
            membership_path(root,a,legacy).write_bytes(b'changed')
            with self.assertRaises(ValueError):membership_path(root,a,legacy)


if __name__=='__main__':unittest.main()
