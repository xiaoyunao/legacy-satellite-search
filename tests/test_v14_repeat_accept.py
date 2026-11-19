import unittest

from scripts.v14_repeat_accept import validate_rows


class TrancheAcceptanceTest(unittest.TestCase):
    def row(self, arm='ls_base'):
        return dict(site='site', trial='0', arm=arm, N_imf='100', N_rendered='50',
                    N_exposed='40', N_final='20', N_psf='15', N_used='10',
                    shared_population_rows_verified='True')

    def test_successful_one_arm_cannot_certify_the_pair(self):
        expected = {('site',0,'ls_base'), ('site',0,'ls_deep')}
        with self.assertRaisesRegex(ValueError, 'missing'):
            validate_rows([self.row()], expected)

    def test_duplicate_arm_cannot_replace_missing_arm(self):
        expected = {('site',0,'ls_base'), ('site',0,'ls_deep')}
        with self.assertRaisesRegex(ValueError, 'duplicating'):
            validate_rows([self.row(), self.row()], expected)

    def test_selected_count_cannot_exceed_psf_denominator(self):
        row = self.row(); row['N_used'] = '16'
        with self.assertRaisesRegex(ValueError, 'denominators'):
            validate_rows([row], {('site',0,'ls_base')})


if __name__ == '__main__':
    unittest.main()
