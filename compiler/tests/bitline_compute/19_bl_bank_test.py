#!/usr/bin/env python3

from test_base import TestBase
import debug


class BlBankTest(TestBase):

    def test_array(self):

        from modules.bitline_compute.bl_bank import BlBank
        debug.info(1, "Test bitline compute single bank")
        a = BlBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_drc_check(a)

    def test_baseline_array(self):
        import tech
        from globals import OPTS
        OPTS.sense_amp = "sense_amp"
        OPTS.sense_amp_tap = "sense_amp_tap"
        OPTS.sense_amp_array = "sense_amp_array"
        OPTS.baseline = True
        OPTS.separate_vdd = True

        tech.drc_exceptions["BlBaselineBank"] = tech.drc_exceptions["min_nwell"]

        from modules.bitline_compute.baseline.bl_baseline_bank import BlBaselineBank

        debug.info(1, "Test bitline compute single bank")
        a = BlBaselineBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_check(a)
        # self.local_drc_check(a)


TestBase.run_tests(__name__)
