import unittest
from pathlib import Path

import yaml

from ls_satsearch.run import read_csv
from scripts.v14_production_masks import analysis_role
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


    def test_outside_calibration_split_uses_its_source_bound_ledger(self):
        # The original manifest roles were deliberately left untouched when
        # the deterministic every-fifth-field development split was frozen.
        fields=yaml.safe_load(Path('configs/v14/cohorts/south_outside_census/fields.yaml').read_text())['fields']
        rows=read_csv(Path('results/v14/discovery/south_outside_census/fields.csv'))
        items=[dict(details={r['field']:r for r in rows})]
        for i,wanted in ((0,'pilot_dev'),(1,'pilot_eval')):
            self.assertEqual(fields[i]['role'],'pilot_eval')
            self.assertEqual(rows[i]['field'],fields[i]['id'])
            self.assertEqual(analysis_role(fields[i]['role'],fields[i]['id'],rows[i]['manifest_sha256'],items),wanted)
        self.assertEqual(analysis_role('pilot_eval',fields[0]['id'],'another-source',items),'pilot_eval')


if __name__=='__main__':unittest.main()
