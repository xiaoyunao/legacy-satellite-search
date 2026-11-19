import tempfile
import unittest
from pathlib import Path

from ls_satsearch.run import publish_peak_cache,read_csv


class PeakStorageTest(unittest.TestCase):
    def test_logical_table_follows_complete_scratch_file_and_replaces_old_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);summary=root/'home';work=root/'scratch'
            summary.mkdir();work.mkdir()
            logical=summary/'deduplicated_peaks.csv';logical.write_text('old copy')
            target=publish_peak_cache(summary,work,[dict(score=8,dm=20)])
            self.assertTrue(logical.is_symlink())
            self.assertEqual(logical.resolve(),target.resolve())
            self.assertEqual(read_csv(logical),[dict(score='8',dm='20')])
            publish_peak_cache(summary,work,[dict(score=9,dm=19)])
            self.assertEqual(read_csv(logical),[dict(score='9',dm='19')])


if __name__=='__main__':unittest.main()
