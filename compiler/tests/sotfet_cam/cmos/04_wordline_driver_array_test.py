#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""

from cam_test_base import CamTestBase
import debug


class SwWordlineDriverArrayTest(CamTestBase):

    @staticmethod
    def make_array(rows):
        from globals import OPTS
        mod = CamTestBase.load_class_from_opts('wordline_driver')
        return mod(rows=rows, buffer_stages=OPTS.wordline_buffers)

    def test_8_rows(self):
        debug.info(2, "Testing 8-row wordline driver array")
        a = self.make_array(rows=8)
        self.local_drc_check(a)

    # def test_256_rows(self):
    #     debug.info(2, "Testing 256-row wordline driver array")
    #     a = self.make_array(rows=256)
    #     self.local_drc_check(a)


CamTestBase.run_tests(__name__)
