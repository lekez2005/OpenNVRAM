#!/usr/bin/env python3
"""
Run a regression test on a tri_gate_array.
"""
from test_base import TestBase
import debug


class TriGateArrayTest(TestBase):

    def test_one_word_per_row(self):
        debug.info(1, "Testing tri_gate_array one word per row")
        from modules.push_rules.tri_gate_array_horizontal import TriGateArray
        a = TriGateArray(columns=32, words_per_row=1)
        self.local_check(a)

    def test_two_words_per_row(self):
        debug.info(1, "Testing tri_gate_array two words per row")
        from modules.push_rules.tri_gate_array_horizontal import TriGateArray
        a = TriGateArray(columns=64, words_per_row=2)
        self.local_check(a)

    def test_four_words_per_row(self):
        debug.info(1, "Testing tri_gate_array four words per row")
        from modules.push_rules.tri_gate_array_horizontal import TriGateArray
        a = TriGateArray(columns=64, words_per_row=4)
        self.local_check(a)


TriGateArrayTest.run_tests(__name__)
