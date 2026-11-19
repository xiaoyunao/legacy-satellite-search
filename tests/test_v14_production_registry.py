import unittest
from scripts.v14_production_registry import eligibility


class HistoricalEligibilityTest(unittest.TestCase):
    def test_followup_and_development_never_become_discoveries(self):
        limits=dict(policy='A_base',budget=.3,main_dm=[16.5,20.75])
        row=dict(role='pilot_eval',policy='A_base',channel='A_base',budget='.3',dm='20')
        self.assertEqual(eligibility(row,'frozen_discovery',limits),'eligible_hypothesis')
        for cls in ('development_regression','followup_index_not_discovery','alternate_distance_branch'):
            self.assertEqual(eligibility(row,cls,limits),cls)
        for change in (dict(role='pilot_dev'),dict(channel='A_deep'),dict(budget='.1'),dict(dm='21')):
            self.assertNotEqual(eligibility(dict(row,**change),'frozen_discovery',limits),'eligible_hypothesis')


if __name__=='__main__':unittest.main()
