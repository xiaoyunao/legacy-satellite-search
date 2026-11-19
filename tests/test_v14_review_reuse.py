import json
import tempfile
import unittest
from pathlib import Path

from ls_satsearch.run import write_csv
from scripts.v14_review import completed_prior_groups


class ReviewReuseTest(unittest.TestCase):
    def test_reuses_only_complete_fits_with_identical_source_hypotheses(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);table=root/'sky_group_candidates.csv';packet=root/'packets/v14/north/00'
            packet.mkdir(parents=True)
            row=dict(group_id='g',field='field',channel='A_base',policy='A_base',budget=.3,
                     ra_deg=10,dec_deg=20,dm=19,rh_arcmin=.5,ranking=8)
            write_csv(table,[row]);write_csv(packet/'review_modes.csv',[row])
            write_csv(packet/'group_review_summary.csv',[dict(group_id='g',modes_fit=1,modes_attempted=1)])
            write_csv(packet/'group_review_modes.csv',[dict(candidate_group_id='g',fit_status='complete')])
            (packet/'provenance.json').write_text(json.dumps(dict(input=str(table))))
            self.assertEqual(completed_prior_groups(table,root=root/'packets'),{'g'})
            self.assertEqual(completed_prior_groups(table,exclude=packet,root=root/'packets'),set())
            write_csv(table,[dict(row,dm=20)])
            self.assertEqual(completed_prior_groups(table,root=root/'packets'),set())


if __name__=='__main__':unittest.main()
