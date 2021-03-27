#!/usr/bin/env python3
"""
Run a regression test on a single transistor column_mux.
"""

from test_base import TestBase
import debug


class ColumnMuxArrayTest(TestBase):

    def test_two_words_per_row(self):
        debug.info(1, "Testing sample for 2-way column_mux_array")
        a = self.create_class_from_opts("column_mux_array", columns=32, word_size=16)
        self.local_check(a)

    def test_four_words_per_row(self):
        debug.info(1, "Testing sample for 4-way column_mux_array")
        a = self.create_class_from_opts("column_mux_array", columns=32, word_size=8)
        self.local_check(a)

    def test_eight_words_per_row(self):
        debug.info(1, "Testing sample for 8-way column_mux_array")
        a = self.create_class_from_opts("column_mux_array", columns=32, word_size=4)
        self.local_check(a)


ColumnMuxArrayTest.run_tests(__name__)
