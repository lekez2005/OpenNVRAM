#!/usr/bin/env python3
"""
Run a regression test on a flop_array.
"""
from test_base import TestBase
import debug


class FlopArrayTest(TestBase):

    def test_one_word_per_row(self):
        debug.info(1, "Testing flop_array one word per row")
        from modules.push_rules.flop_array_horizontal import FlopArray
        a = FlopArray(columns=32, words_per_row=1)
        self.local_check(a)

    def test_two_words_per_row(self):
        debug.info(1, "Testing flop_array two words per row")
        from modules.push_rules.flop_array_horizontal import FlopArray
        a = FlopArray(columns=64, words_per_row=2)
        self.local_check(a)

    def test_four_words_per_row(self):
        debug.info(1, "Testing flop_array four words per row")
        from modules.push_rules.flop_array_horizontal import FlopArray
        a = FlopArray(columns=64, words_per_row=4)
        self.local_check(a)


FlopArrayTest.run_tests(__name__)
