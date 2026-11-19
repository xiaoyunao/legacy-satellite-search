import unittest

import numpy as np

from scripts.v14_repeat_statistics import resample, simultaneous_paired_bound


class SharedPhysicalPopulationTest(unittest.TestCase):
    def test_identical_skies_do_not_create_three_independent_populations(self):
        values = np.tile(np.array([0,0,0,0,1,1,1,1])[None,:,None], (3,1,6))
        draws = resample(values, 20000, 487430)
        # Eight Bernoulli(1/2) block draws have variance .25/8,
        # regardless of repeating those same populations in three skies.
        self.assertAlmostEqual(float(draws[:,0].var()), .25/8, delta=.001)
        self.assertTrue(np.array_equal(draws[:,0], draws[:,-1]))

    def test_no_discordances_do_not_imply_no_monte_carlo_uncertainty(self):
        low, high = simultaneous_paired_bound(np.zeros((3,8,6),dtype=int))
        self.assertTrue(np.all(low < 0))
        self.assertTrue(np.all(high > 0))


if __name__ == '__main__':
    unittest.main()
