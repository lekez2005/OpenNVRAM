#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""

from cam_test_base import CamTestBase


class MlSearchSenseArrayTest(CamTestBase):

    def test_8_rows(self):
        self.debug.info(2, "Testing 8-row search matchline sense amp array")
        a = self.create_class_from_opts("search_sense_amp_array", rows=8)
        self.local_check(a)

    def test_256_rows(self):
        self.debug.info(2, "Testing 256-row search matchline sense amp array")
        a = self.create_class_from_opts("search_sense_amp_array", rows=256)
        self.local_check(a)


CamTestBase.run_tests(__name__)
