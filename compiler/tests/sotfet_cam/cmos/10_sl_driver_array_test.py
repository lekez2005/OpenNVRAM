#!/usr/bin/env python3
"""
Run a regression test on a write driver array
"""

from cam_test_base import CamTestBase
import debug


class SearchLineDriverTest(CamTestBase):

    def runTest(self):
        from modules.cam.sl_driver_array import sl_driver_array

        debug.info(2, "Testing search line driver array for columns=8, word_size=8")
        a = sl_driver_array(columns=8, word_size=8)
        self.local_check(a)

        debug.info(2, "Testing search line driver array for columns=64, word_size=64")
        a = sl_driver_array(columns=64, word_size=64)
        self.local_check(a)
        

CamTestBase.run_tests(__name__)
