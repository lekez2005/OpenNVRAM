#!/usr/bin/env python3
"""
Run a regression test on a flop_array.
"""
from test_base import TestBase
import debug


class WriteDriverArrayTest(TestBase):

    def test_one_word_per_row(self):
        debug.info(1, "Testing write_driver_array one word per row")
        from modules.push_rules.write_driver_array_horizontal import WriteDriverArray
        a = WriteDriverArray(columns=32, words_per_row=1)
        self.local_check(a)

    def test_two_words_per_row(self):
        debug.info(1, "Testing write_driver_array two words per row")
        from modules.push_rules.write_driver_array_horizontal import WriteDriverArray
        a = WriteDriverArray(columns=64, words_per_row=2)
        self.local_check(a)

    def test_four_words_per_row(self):
        debug.info(1, "Testing write_driver_array four words per row")
        from modules.push_rules.write_driver_array_horizontal import WriteDriverArray
        a = WriteDriverArray(columns=64, words_per_row=4)
        self.local_check(a)


WriteDriverArrayTest.run_tests(__name__)
