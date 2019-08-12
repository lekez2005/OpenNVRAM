#!/usr/bin/env python3
"""
Run a regression test on a basic array
"""

from cam_test_base import CamTestBase


class CamBitcellArrayTest(CamTestBase):

    def test_32x32_array(self):
        from modules.cam.cam_bitcell_array import cam_bitcell_array

        self.debug.info(2, "Testing 4x4 array for cam_cell_6t")
        a = cam_bitcell_array(name="cam_bitcell_array", cols=32, rows=32)
        self.local_check(a)


CamTestBase.run_tests(__name__)
