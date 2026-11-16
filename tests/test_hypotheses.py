from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.hypotheses import group_candidates, template_branch
from ls_satsearch.search import deduplicate, load_isochrone


class SearchHypothesesTest(unittest.TestCase):
    def test_compact_and_distant_survive_broad_anchor(self):
        rows = [dict(method='B', score=s, dm=d, rh_arcmin=r, x=x, y=0)
                for s,d,r,x in [(22,22.25,16,6),(18,20.,1,0),(17,20.25,1,.25),
                                (16,19.25,1,0),(15,20.,16,.25),(14,16.25,1,0)]]
        peaks = deduplicate(rows)
        self.assertEqual(len(peaks),5)
        self.assertEqual(rows[1]['dedup_rank'], rows[2]['dedup_rank'])
        self.assertNotEqual(rows[1]['dedup_rank'], rows[3]['dedup_rank'])
        self.assertNotEqual(rows[1]['dedup_rank'], rows[4]['dedup_rank'])
        self.assertEqual([template_branch(d) for d in (16.25,16.5,20.75,21)],
                         ['near','main','main','far'])

    def test_group_retains_distance_solutions(self):
        rows = [dict(field_id='demo', x=x, y=0, rh_arcmin=1, branch='main',
                     method=m, depth=d, dm=mu) for x,m,d,mu in
                [(0,'A','base',19.5),(.4,'B','deep',20.5),(5,'A','deep',20)]]
        group_candidates(rows)
        self.assertEqual(rows[0]['candidate_group_id'],rows[1]['candidate_group_id'])
        self.assertNotEqual(rows[0]['candidate_group_id'],rows[2]['candidate_group_id'])

    def test_zahb_break_keeps_imf_rows(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'model.dat'
            path.write_text('# M_ini g r int_IMF stage\n'
                            '0.7 1 0 1 3\n0.8 -2 -3 2 4\n'
                            '0.8 1 2 2 4\n0.81 0.9 1.9 3 4\n'
                            '0.83 0 1 4 4\n')
            native, imf, new=load_isochrone(path)
            old_native, old_imf, old=load_isochrone(path,legacy_locus=True)
            np.testing.assert_array_equal(native,old_native)
            np.testing.assert_array_equal(imf,old_imf)
            middle=(native[1]+native[2])/2
            self.assertLess(cKDTree(old).query(middle)[0],.02)
            self.assertGreater(cKDTree(new).query(middle)[0],.4)


if __name__ == '__main__':
    unittest.main()
