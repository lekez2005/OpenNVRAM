#!/usr/bin/env python3
"""
Run a regression test on a write driver array
"""

from cam_test_base import CamTestBase
import debug


class WriteDriverTest(CamTestBase):

    def runTest(self):
        from modules.cam.cam_write_driver_array import cam_write_driver_array

        debug.info(2, "Testing write_driver_array for columns=8, word_size=8")
        a = cam_write_driver_array(columns=8, word_size=8)
        self.local_check(a)

        debug.info(2, "Testing write_driver_array for columns=64, word_size=64")
        a = cam_write_driver_array(columns=64, word_size=64)
        self.local_check(a)
        

CamTestBase.run_tests(__name__)
