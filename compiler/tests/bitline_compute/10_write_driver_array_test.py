#!/usr/bin/env python3
"""
Run a regression test on a write driver array.
"""

from test_base import TestBase
import debug


class WriteDriverArrayTest(TestBase):

    def test_64_columns(self):
        debug.info(2, "Testing 64-row write driver array")
        a = self.create_class_from_opts("write_driver_array", columns=64, word_size=64)
        self.local_check(a)


TestBase.run_tests(__name__)
