#!/usr/bin/env python3
"""
Run a regression test on a bitline ALU.
"""

from test_base import TestBase


class BitlineAluTest(TestBase):
    def test_bitline_alu(self):
        from globals import OPTS
        from modules.bitline_compute.bit_serial_alu import BitSerialALU
        from modules.bitline_compute.bitline_alu import BitlineALU
        from modules.bitline_compute.bl_bank import BlBank

        OPTS.run_optimizations = False

        num_words = 32
        words_per_row = 2
        word_size = 16
        num_cols = word_size * words_per_row

        bank = BlBank(name="bank1", word_size=num_cols, num_words=num_words, words_per_row=1)

        if OPTS.serial:
            a = BitSerialALU(bank=bank, num_cols=num_cols)
        else:
            a = BitlineALU(bank=bank, num_cols=num_cols, word_size=word_size, cells_per_group=1)

        self.local_check(a)


TestBase.run_tests(__name__)
