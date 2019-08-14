#!/usr/bin/env python3
"""
Run a regression test on a 1 bank SRAM
"""

from test_base import TestBase
import debug


class CamTest(TestBase):

    def test_single_bank(self):
        from modules.bitline_compute.bl_sram import BlSram

        debug.info(1, "One-bank SRAM")
        a = BlSram(word_size=64, num_words=64, num_banks=1, words_per_row=1, name="sram1")
        self.local_drc_check(a)
        #self.local_check(a, final_verification=False)


TestBase.run_tests(__name__)
