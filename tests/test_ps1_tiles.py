"""Allow repeated objects at a MAST page boundary while checking progress."""

import unittest

from ls_satsearch.ps1_tiles import boundary_repeats


class PaginationTest(unittest.TestCase):
    def test_tied_boundary_with_forward_progress(self):
        self.assertEqual(boundary_repeats([6, 7, 9], 6, 3),1)
        self.assertEqual(boundary_repeats([6], 6, 3),1)

    def test_reversed_or_stalled_page(self):
        for ids in ([5, 7, 9], [6, 6, 6], [8, 7, 9]):
            with self.assertRaises(ValueError):
                boundary_repeats(ids,6,3)


if __name__=='__main__':
    unittest.main()
