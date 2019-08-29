#!/usr/bin/env python3
"""
Run a regression test on a write driver array.
"""

from test_base import TestBase
import debug


class WriteDriverArrayTest(TestBase):

    @staticmethod
    def make_array(columns):
        from modules.bitline_compute.write_driver_mask_array import write_driver_mask_array
        return write_driver_mask_array(columns=columns, word_size=columns)

    def test_64_columns(self):
        debug.info(2, "Testing 64-row write driver array")
        a = self.make_array(columns=64)
        self.local_check(a)


TestBase.run_tests(__name__)
