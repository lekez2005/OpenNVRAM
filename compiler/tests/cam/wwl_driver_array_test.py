#!/usr/bin/env python2.7

from cam_test_base import CamTestBase, run_tests

import debug


class WwlDriverArrayTest(CamTestBase):

    def test_block(self):
        from modules.cam import wwl_driver_array
        debug.info(2, "Create WWL driver array")
        a = wwl_driver_array.WwlDriverArray(rows=32, buffer_stages=[1, 3, 8], no_cols=32)
        self.local_check(a)


run_tests(__name__)
