import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from astropy.coordinates import SkyCoord
import numpy as np
import yaml

from ls_satsearch.data import regional_primary
from ls_satsearch.paper_diagnostic import conditional_z, smooth_density
from ls_satsearch.regional_pilot import combine


class RegionalAndDisplayTest(unittest.TestCase):
    def test_one_primary_region_on_both_sides_of_seam(self):
        ra = np.array([193.,193.,8.,8.,90.])
        dec = np.array([32.374,32.375,32.374,32.375,60.])
        expected = (dec>=32.375)&(SkyCoord(ra,dec,unit='deg').galactic.b.deg>=0)
        np.testing.assert_array_equal(regional_primary(ra,dec,'north'),expected)
        np.testing.assert_array_equal(regional_primary(ra,dec,'south'),~expected)

    def test_exposure_normalization_preserves_uniform_density_near_hole(self):
        area = np.ones((60,60))
        area[25:35,25:35] = 0
        density = smooth_density(3*area,area,2,1.)
        self.assertTrue(np.isnan(density[25:35,25:35]).all())
        self.assertTrue(np.isfinite(density[24,30]))
        np.testing.assert_allclose(density[np.isfinite(density)],3.)

    def test_local_binomial_display_uses_area_and_sign(self):
        on=np.array([0,4,0])
        off=np.array([0,0,4])
        a=np.array([1.,1.,1.])
        b=np.array([1.,1.,1.])
        z=conditional_z(on,off,a,b)
        self.assertEqual(z[0],0)
        self.assertAlmostEqual(z[1],-z[2])
        self.assertGreater(z[1],0)

    def test_frozen_yaml_field_matches_json_manifest(self):
        spec=dict(id='test',role='pilot_eval',proxy_census_fractions={3:.8},proxy_area_deg2=1.)
        cfg=dict(seeing=[1.,1.,1.],depth5_dered=[23.,23.,23.])
        record=dict(field=spec,status='complete',observing_conditions_source_sample={'G':cfg,'R':cfg},
                    area_deg2=1.,slurm_job_id='1',wall_seconds=10.,model_sha256='model',fields_sha256='fields',
                    cutflow={n:1 for n in ('inner_psf','inner_other','inner_psf_faint','inner_other_faint')})
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            fields=base/'fields.yaml'
            fields.write_text(yaml.safe_dump(dict(fields=[spec])))
            summary=base/'summary'
            folder=summary/'test-base'
            folder.mkdir(parents=True)
            (folder/'manifest.json').write_text(json.dumps(record))
            with patch('ls_satsearch.regional_pilot.evaluate') as score:
                combine(summary,fields,base/'output',policy=base/'frozen.json')
            score.assert_called_once()
