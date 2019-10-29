#!/usr/bin/env python3
"""
Run a regression test on a 1 bank SRAM
"""

from test_base import TestBase
import debug


class SramTest(TestBase):

    def test__sram(self):
        from modules.bitline_compute.bl_sram import BlSram
        from modules.bitline_compute.bs_sram import BsSram
        from modules.bitline_compute.baseline.baseline_sram import BaselineSram
        from globals import OPTS

        if OPTS.baseline:
            test_class = BaselineSram
        elif OPTS.serial:
            test_class = BsSram
        else:
            test_class = BlSram

        OPTS.run_optimizations = False

        debug.info(1, "One-bank SRAM")
        a = test_class(word_size=256, num_words=128, num_banks=1, words_per_row=1, name="sram1")
        # self.local_check(a, final_verification=not OPTS.separate_vdd)
        self.local_check(a, final_verification=False)


TestBase.run_tests(__name__)
