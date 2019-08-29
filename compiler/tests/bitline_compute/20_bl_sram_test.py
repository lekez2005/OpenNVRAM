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

    def test_baseline_sram(self):
        import tech
        from globals import OPTS
        OPTS.sense_amp = "sense_amp"
        OPTS.sense_amp_tap = "sense_amp_tap"
        OPTS.sense_amp_array = "sense_amp_array"
        OPTS.baseline = True
        OPTS.separate_vdd = True
        from modules.bitline_compute.baseline.bl_baseline_sram import BlBaselineSram

        tech.drc_exceptions["BlBaselineSram"] = tech.drc_exceptions["min_nwell"]

        debug.info(1, "One-bank Baseline SRAM")
        a = BlBaselineSram(word_size=64, num_words=64, num_banks=1, words_per_row=1, name="sram1")
        self.local_drc_check(a)
        #self.local_check(a, final_verification=False)


TestBase.run_tests(__name__)
