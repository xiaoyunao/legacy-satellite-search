"""Long angular chains must not become a single human-review object."""
import unittest

from ls_satsearch.expansion import unit
from scripts.v14_bounded_review_geometry import bounded_groups


class BoundedReviewGeometryTest(unittest.TestCase):
    def test_chain_preserves_all_positions_without_transitive_merge(self):
        points = unit([0, 4/60, 8/60], [0, 0, 0])
        groups = bounded_groups(points, ['a', 'b', 'c'])
        self.assertEqual(groups, [[0, 1], [2]])
        self.assertEqual(sorted(i for g in groups for i in g), [0, 1, 2])

    def test_spherical_wrap_and_pole(self):
        for ra, dec in [([359.99, .01], [0, 0]), ([0, 180], [89.99, 89.99])]:
            self.assertEqual(len(bounded_groups(unit(ra, dec), ['a', 'b'])), 1)

    def test_input_order_cannot_change_packet_membership(self):
        keys = ['a', 'b', 'c', 'd']
        points = unit([0, 4/60, 8/60, 20], [0]*4)
        expected = {frozenset(keys[i] for i in g) for g in bounded_groups(points, keys)}
        order = [2, 0, 3, 1]
        shuffled = [keys[i] for i in order]
        actual = {frozenset(shuffled[i] for i in g)
                  for g in bounded_groups(points[order], shuffled)}
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
