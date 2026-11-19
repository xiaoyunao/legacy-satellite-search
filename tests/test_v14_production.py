import unittest

from scripts.v14_production import eligibility, select


class ProductionAuditTest(unittest.TestCase):
    def row(self, **changes):
        return dict(dict(source_kind='blind_peak',input='results/v14/discovery/north/main/sky_group_candidates.csv',
                         role='pilot_eval',channel='A_base',policy='A_base',budget='0.3',
                         branch='main',dm='20.75',detection_id='primary'), **changes)

    def test_development_alternatives_and_far_modes_do_not_enter_production(self):
        self.assertEqual(eligibility(self.row()),'eligible')
        for changes in (dict(role='pilot_dev'),dict(channel='A_deep'),dict(policy='A_union'),
                        dict(budget='0.1'),dict(dm='21.0'),dict(dm='nan'),dict(branch='far'),
                        dict(input='results/v13/discovery/v13/north/main/sky_group_candidates.csv')):
            with self.subTest(changes=changes):
                self.assertNotEqual(eligibility(self.row(**changes)),'eligible')

    def test_c_review_from_an_excluded_record_does_not_leak_into_primary(self):
        modes=[self.row(), self.row(detection_id='strict',budget='0.1'),
               dict(source_kind='C_followup',detection_id='strict',fit_status='complete',c_ts='99')]
        selected, reviewed=select(modes)
        self.assertEqual(len(selected),1)
        self.assertEqual(reviewed,set())
        modes.append(dict(source_kind='C_followup',detection_id='primary',fit_status='complete',c_ts='0'))
        self.assertEqual(select(modes)[1],{'primary'})


if __name__ == '__main__':
    unittest.main()
