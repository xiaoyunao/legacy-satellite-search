import unittest
from scripts.v14_shortlist import choose_priority, separation


class ShortlistTest(unittest.TestCase):
    def test_wrap_and_pole_are_spherical(self):
        self.assertAlmostEqual(separation(dict(ra_deg=359.99,dec_deg=0),dict(ra_deg=.01,dec_deg=0)),1.2)
        self.assertLess(separation(dict(ra_deg=0,dec_deg=89.99),dict(ra_deg=180,dec_deg=89.99)),1.21)

    def test_interleaves_cohorts_and_rejects_duplicate_positions(self):
        def row(ra):return dict(ra_deg=ra,dec_deg=0)
        pools=dict(north=[row(0),row(.01),row(1)],south=[row(2),row(3)])
        result=choose_priority(pools,4,5.)
        self.assertEqual([r['ra_deg'] for r in result],[0,2,1,3])
        self.assertEqual(len(pools['north']),3)
