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
        words_per_row = 1
        word_size = 256
        alu_word_size = 32
        num_cols = word_size * words_per_row

        bank = BlBank(name="bank1", word_size=num_cols, num_words=num_words, words_per_row=1)

        if OPTS.serial:
            a = BitSerialALU(bank=bank, num_cols=num_cols)
        else:
            a = BitlineALU(bank=bank, num_cols=num_cols, word_size=alu_word_size,
                           cells_per_group=OPTS.alu_cells_per_group)

        self.local_check(a)


TestBase.run_tests(__name__)
