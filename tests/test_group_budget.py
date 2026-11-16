"""Regression checks for review-cost calibration and blind distance selection."""

import unittest

from ls_satsearch.group_budget import cut, groups, matches


class GroupBudgetTest(unittest.TestCase):
    @staticmethod
    def peak(x, dm, score):
        return dict(x=x,y=0,ra_deg=180+x/60,dec_deg=0,dm=dm,rh_arcmin=.5,
                    channel='A_base',score=score,ranking=score)

    def test_repeated_templates_use_one_review_slot(self):
        rows = [self.peak(0,19.5,10),self.peak(.4,18.75,8),self.peak(5,18,7)]
        grouped = groups(rows)
        cutoff, target = cut([a['ranking'] for a,_ in grouped],10,.1)
        self.assertEqual(target,1)
        self.assertEqual(sum(a['ranking'] >= cutoff for a,_ in grouped),1)
        match = matches(grouped,dict(ra_deg=180,dec_deg=0,D_kpc=50,theta_h_arcmin=.5),
                        cutoff,dict(match_min_arcmin=2,match_rh_factor=1,match_dm_tolerance=.75))
        self.assertTrue(match['spatial'])
        self.assertFalse(match['blind_correct'])
        self.assertFalse(match['correct_mode_exists'])
        alternative = self.peak(.4,18.5,8)
        grouped = groups([rows[0],alternative,rows[2]])
        match = matches(grouped,dict(ra_deg=180,dec_deg=0,D_kpc=50,theta_h_arcmin=.5),
                        cutoff,dict(match_min_arcmin=2,match_rh_factor=1,match_dm_tolerance=.75))
        self.assertTrue(match['correct_mode_exists'])
        self.assertFalse(match['blind_correct'])

    def test_below_cut_hypothesis_does_not_move_anchor(self):
        primary = self.peak(0,19,8)
        secondary = self.peak(.9,18,3)
        other = self.peak(1.8,20,7)
        self.assertEqual([a for a,_ in groups([secondary,other,primary])],[primary,other])


if __name__ == '__main__':
    unittest.main()
