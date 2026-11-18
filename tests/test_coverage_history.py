import tempfile
import unittest
from pathlib import Path

import numpy as np

from ls_satsearch.coverage_history import covered, find_local
from ls_satsearch.data import Field, sample_pixels
from ls_satsearch.expansion import field_bounds


class HistoryRasterTest(unittest.TestCase):
    def test_polar_bounding_box_retains_valid_sky_without_validating_outside_pixels(self):
        field=Field(36.,-87.50452633052011,3.154913339498665,1/6,buffer=0)
        bounds=field_bounds(field)
        self.assertTrue(np.isfinite(bounds).all())
        self.assertEqual(bounds[2],-90.)
        with np.errstate(invalid='ignore'):
            _,invalid_dec=field.sky(0,-field.width*30)
        self.assertTrue(np.isnan(invalid_dec))
        record=dict(geometry=[field.ra,field.dec,field.width,field.step,0],bounds=bounds,
                    previous=None,survey=0,raster='polar.npy',cache='polar')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            np.save(path/'polar.npy',np.ones((field.n,field.n),dtype=bool))
            np.testing.assert_array_equal(covered(path,[record],np.array([36.,200.]),
                                          np.array([-89.,-89.])),[True,False])

    def test_nonpolar_bounding_box_matches_projection(self):
        field=Field(165.,32.,3.5,1/6,buffer=0)
        bounds=field_bounds(field)
        np.testing.assert_allclose(bounds[2:],[field.sky(0,-105)[1],field.sky(0,105)[1]],rtol=0,atol=1e-13)

    def test_geometric_box_does_not_erase_an_unmeasured_hole(self):
        field = Field(359.9, 2., 1., .5, buffer=0)
        ra = np.array([359.91, .03, 12.])
        dec = np.array([2.01, 2.01, 2.01])
        coverage = np.ones((field.n, field.n), dtype=bool)
        hole = sample_pixels(field, coverage, *field.xy(ra[:1], dec[:1]))
        coverage[hole] = False
        record = dict(region='south', geometry=[field.ra, field.dec, field.width, field.step, 0],
                      bounds=field_bounds(field), survey=3, previous=None, cache='prior')
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            folder = data/'cache/prior'
            folder.mkdir(parents=True)
            np.save(folder/'coverage.npy', coverage)
            self.assertEqual(find_local([record], 0, .25, 1., 3., 'south'), [0])
            self.assertEqual(find_local([record], 0, .25, 1., 3., 'north'), [])
            np.testing.assert_array_equal(covered(data, [record], ra, dec), [False, True, False])
            accepted = {3: np.array([True, False, True])}
            np.testing.assert_array_equal(covered(data, [record], ra, dec, accepted), [False, False, False])

    def test_primary_quality_uses_brick_metadata_on_native_coordinates(self):
        from ls_satsearch.coverage_history import residual_ownership

        field = Field(5., -42., 1., .5, buffer=0)
        columns = ('RA', 'DEC', 'RA1', 'RA2', 'DEC1', 'DEC2', 'EBV', 'PSFSIZE_G',
                   'PSFSIZE_R', 'PSFDEPTH_G', 'PSFDEPTH_R')
        bricks = np.array([(5., -42., 4.8, 5.2, -42.2, -41.8, .04, 1.1, 1.2, 24, 24)],
                          dtype=[(k, 'f8') for k in columns])
        plan = dict(partition=dict(ra_lo=4.,ra_hi=6.,dec_lo=-43.,dec_hi=-41.),
                    quality='primary', abs_b=25, ebv=.1)
        positions = (np.array([5., 6.]),np.array([-42., -42.]))
        selected = residual_ownership(*positions,dict(ownership=plan),Path('/unused'),'south',bricks,field)
        np.testing.assert_array_equal(selected,[True,False])
        bricks['EBV'] = .14
        rejected = residual_ownership(*positions,dict(ownership=plan),Path('/unused'),'south',bricks,field)
        np.testing.assert_array_equal(rejected,[False,False])
