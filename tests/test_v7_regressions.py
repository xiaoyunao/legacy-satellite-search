import unittest

import numpy as np

from ls_satsearch.data import Field
from ls_satsearch.expansion import core_disjoint, field_bounds
from ls_satsearch.hsc_depth_audit import image_stamp


class SeventhRoundRegressions(unittest.TestCase):
    def test_stamp_preserves_aperture_flux_at_different_sampling(self):
        y,x=np.mgrid[:101,:101]
        source=np.exp(-((x-50)**2+(y-50)**2)/(2*4**2)).astype(np.float32)
        native=source.sum()
        output_axis=50+(np.arange(61)-30)*1.5
        rx,ry=np.meshgrid(output_axis,output_axis)
        stamp=image_stamp(source,np.column_stack((rx.ravel(),ry.ravel())),61,1.,1.5**2,1.)
        self.assertAlmostEqual(float(stamp.sum()/native),1.,places=2)

    def test_disjoint_rotated_ra_interval(self):
        base=field_bounds(Field(359.7,25.,2.,1/6,buffer=0))
        close=field_bounds(Field(.6,25.,2.,1/6,buffer=0))
        far=field_bounds(Field(3.3,25.,2.,1/6,buffer=0))
        separated=field_bounds(Field(.6,28.0,2.,1/6,buffer=0))
        self.assertFalse(core_disjoint(close,[base]))
        self.assertTrue(core_disjoint(far,[base]))
        self.assertTrue(core_disjoint(separated,[base]))


if __name__ == '__main__':
    unittest.main()
