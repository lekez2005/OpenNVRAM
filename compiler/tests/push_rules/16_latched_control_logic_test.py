#!/usr/bin/env python3
"""
Run a regression test on a latched control logic module.
"""
from types import SimpleNamespace

from test_base import TestBase


class LatchedControlLogicTest(TestBase):
    def test_one_row(self):
        self.run_buffer_test(words_per_row=1, rows=1)

    def test_two_rows(self):
        self.run_buffer_test(words_per_row=1, rows=2)

    def test_two_words_per_rows(self):
        self.run_buffer_test(words_per_row=2, rows=2)

    def test_left_bank(self):
        self.run_buffer_test(is_left_bank=True)

    def run_buffer_test(self, is_left_bank=False, words_per_row=1, num_banks=1, rows=2):
        from modules.push_rules.latched_control_logic import LatchedControlLogic
        from globals import OPTS

        num_banks = 2 if is_left_bank else num_banks

        OPTS.num_banks = num_banks
        OPTS.control_buffers_num_rows = rows
        OPTS.create_decoder_clk = True
        bank = SimpleNamespace(is_left_bank=is_left_bank, words_per_row=words_per_row)
        a = LatchedControlLogic(bank)
        self.local_check(a)


LatchedControlLogicTest.run_tests(__name__)
