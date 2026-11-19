import unittest
from scripts.v14_shortlist_context import positions


class ContextCentreTest(unittest.TestCase):
    def test_discovery_and_fitted_centres_are_kept_separate(self):
        case=dict(case_id='P001',cohort='north',ra_deg='1',dec_deg='2',highest_dm='19')
        fits=[dict(fit_status='complete',rank='7',fit_ra_deg='1.1',fit_dec_deg='2.1',fit_dm='19.25'),
              dict(fit_status='unavailable')]
        rows=positions(case,fits)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['ra_deg'],'1')
        self.assertEqual(rows[1]['ra_deg'],'1.1')
        self.assertEqual(rows[1]['position_type'],'C_refit')
