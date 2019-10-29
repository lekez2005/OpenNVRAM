#!/usr/bin/env python3
"""
Run a regression test on a bitline ALU.
"""

from test_base import TestBase


class BitlineAluTest(TestBase):
    def test_bitline_alu(self):
        from globals import OPTS
        from modules.bitline_compute.bitline_alu import BitlineALU
        from modules.bitline_compute.bl_bank import BlBank

        OPTS.run_optimizations = False

        OPTS.configure_sense_amps(OPTS.MIRROR_SENSE_AMP)

        num_cols = 32
        num_words = 32

        bank = BlBank(name="bank", word_size=num_cols, num_words=num_words, words_per_row=1)

        a = BitlineALU(bank=bank, num_cols=num_cols, word_size=32, cells_per_group=1)
        self.local_check(a)


TestBase.run_tests(__name__)
