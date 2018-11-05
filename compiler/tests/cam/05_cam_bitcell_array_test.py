#!/usr/bin/env python2.7
"""
Run a regresion test on a basic array
"""

from cam_test_base import CamTestBase, run_tests
import debug


class CamBitcellArrayTest(CamTestBase):

    def test_4x4_array(self):

        from modules.cam import cam_bitcell_array

        debug.info(2, "Testing 4x4 array for cam_cell_6t")
        a = cam_bitcell_array.cam_bitcell_array(name="cam_bitcell_array", cols=4, rows=4)
        self.local_check(a)


run_tests(__name__)
