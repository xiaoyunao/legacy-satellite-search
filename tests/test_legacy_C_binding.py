import os
from pathlib import Path
import tempfile
import unittest

from ls_satsearch.run import write_csv
from scripts.v14_catalog import load_modes


class LegacyCBindingTest(unittest.TestCase):
    def test_same_group_label_cannot_certify_a_changed_source_seed(self):
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory);folder=Path('results/v4/holdout');folder.mkdir(parents=True)
                source=folder/'sky_group_candidates.csv'
                seed=dict(group_id='g',field='f',policy='A_base',channel='A_base',budget=.3,
                    ra_deg=10,dec_deg=20,dm=20,rh_arcmin=.5,ranking=8,score=8,peak_rank=1)
                fit=dict(candidate_group_id='g',field='f',rank=1,fit_status='complete',seed_dm=20,
                    seed_rh_arcmin=.5,fit_dm=20,fit_rh_arcmin=.5,fit_ra_deg=10,fit_dec_deg=20,
                    ts=10,C_refit_TS_without_top3=2,discovery_score=8)
                write_csv(source,[seed]);write_csv(folder/'group_review_modes.csv',[fit])
                write_csv(folder/'group_review_summary.csv',[dict(group_id='g',best_ts=10,best_dm=20)])
                no_proof,modes=load_modes([source])
                self.assertIsNone(no_proof[0]['c_ts'])
                self.assertEqual(modes[-1]['source_kind'],'C_unbound_context')
                write_csv(folder/'reviewed_group_inputs.csv',[seed])
                bound,modes=load_modes([source]);self.assertEqual(bound[0]['c_ts'],10)
                self.assertEqual(modes[-1]['source_kind'],'C_followup')
                write_csv(source,[dict(seed,ra_deg=11)])
                changed,modes=load_modes([source]);self.assertIsNone(changed[0]['c_ts'])
                self.assertEqual(modes[-1]['source_kind'],'C_unbound_context')
            finally:os.chdir(previous)


if __name__=='__main__':unittest.main()
