import unittest
from unittest.mock import patch
from pathlib import Path
import yaml
from scripts.v13_image_trials import photon_seed
from scripts.v14_repeat import conditions, task


class RepeatTest(unittest.TestCase):
    def test_grid_and_fixed_initial_tasks(self):
        plan=yaml.safe_load(Path('configs/v14_repeat/protocol.yaml').read_text())
        grid=conditions(plan)
        self.assertEqual(len(grid),48)
        self.assertEqual(len({tuple(c) for c in grid}),6)
        self.assertEqual(task(1),('v14_south_response_1','trial02'))
        with self.assertRaises(ValueError):task(9)

    def test_repeats_have_distinct_reproducible_photon_noise(self):
        seeds=[photon_seed(487219,i) for i in range(48)]
        self.assertEqual(len(set(seeds)),48)
        self.assertEqual(seeds,[photon_seed(487219,i) for i in range(48)])

    def test_prepare_refuses_legacy_namespace_before_writes(self):
        from scripts.v14_repeat import prepare
        with patch('scripts.v13_image_trials.VERSION','v13'):
            with self.assertRaisesRegex(ValueError,'refusing to modify a legacy experiment'):
                prepare()
