from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from astropy.io import fits
from astropy.wcs import WCS
import numpy as np

from scripts import v12_footprint
with patch.dict(sys.modules,{'v12_footprint':v12_footprint}):
    from scripts.v14_image0706 import read_image


class ImageSupportTest(unittest.TestCase):
    def test_native_coadd_support_keeps_resolved_regions_and_removes_unmeasured_pixels(self):
        header=WCS(naxis=2).to_header()
        image=np.ones((20,20));weight=np.ones_like(image)
        weight[3,4]=0
        bits=np.zeros(image.shape,dtype=np.int32)
        bits[5,6]=1<<13;bits[7,8]=1<<17;bits[9,10]=1<<19
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/'legacysurvey-test-image-g.fits.fz'
            fits.PrimaryHDU(image,header=header).writeto(path)
            fits.PrimaryHDU(weight).writeto(root/'legacysurvey-test-invvar-g.fits.fz')
            fits.PrimaryHDU(bits).writeto(root/'legacysurvey-test-maskbits.fits.fz')
            measured,_,_=read_image(path)
            self.assertTrue(np.isnan(measured[3,4]))
            self.assertTrue(np.isnan(measured[9,10]))
            self.assertEqual(measured[5,6],1)
            self.assertEqual(measured[7,8],1)
