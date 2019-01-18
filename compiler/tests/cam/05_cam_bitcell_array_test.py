#!/usr/bin/env python3
"""
Run a regression test on a basic array
"""

from cam_test_base import CamTestBase


class CamBitcellArrayTest(CamTestBase):

    def test_4x4_array(self):
        from globals import OPTS
        if not OPTS.bitcell_array == "cam_bitcell_array":
            return

        from modules.cam import cam_bitcell_array

        self.debug.info(2, "Testing 4x4 array for cam_cell_6t")
        a = cam_bitcell_array.cam_bitcell_array(name="cam_bitcell_array", cols=4, rows=4)
        self.local_check(a)


CamTestBase.run_tests(__name__)
