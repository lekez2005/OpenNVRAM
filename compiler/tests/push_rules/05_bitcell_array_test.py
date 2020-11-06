#!/usr/bin/env python3
"""
Run a regression test on a basic bitcell array
"""

from test_base import TestBase
import debug


class BitcellArrayTest(TestBase):

    def test_small_array(self):
        from modules.push_rules.push_bitcell_array import push_bitcell_array

        debug.info(2, "Testing 8x4 array for push rule_cell")
        a = push_bitcell_array(name="bitcell_array", cols=4, rows=8)
        self.local_check(a)

    def test_wide_array(self):
        from modules.push_rules.push_bitcell_array import push_bitcell_array

        debug.info(2, "Testing 64x128 array for push rule_cell")
        a = push_bitcell_array(name="bitcell_array", cols=128, rows=64)
        self.local_check(a)

    def test_high_array(self):
        from modules.push_rules.push_bitcell_array import push_bitcell_array

        debug.info(2, "Testing 256x64 array for push rule_cell")
        a = push_bitcell_array(name="bitcell_array", cols=64, rows=256)
        self.local_check(a)


BitcellArrayTest.run_tests(__name__)
