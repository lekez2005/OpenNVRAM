#!/usr/bin/env python3
"""
Run a regression test on a write driver array.
"""


from test_base import TestBase
import debug


class SenseAmpArrayTest(TestBase):

    @staticmethod
    def make_array(columns):
        from modules.bitline_compute.write_driver_mask_array import write_driver_mask_array
        return write_driver_mask_array(columns=columns, word_size=columns)

    def test_regular_sense_amp(self):
        from modules.sense_amp_array import sense_amp_array
        import tech
        tech.drc_exceptions["sense_amp_array"] = tech.drc_exceptions["min_nwell"]
        from globals import OPTS
        debug.info(2, "Testing 64-col sense amp driver")
        OPTS.sense_amp = "sense_amp"
        OPTS.sense_amp_tap = "sense_amp_tap"

        a = sense_amp_array(word_size=64, words_per_row=1)
        self.local_check(a)

    def test_dual_sense_amp(self):
        import tech
        from modules.bitline_compute.dual_sense_amp_array import dual_sense_amp_array
        tech.drc_exceptions["sense_amp_array"] = tech.drc_exceptions["min_nwell"]
        debug.info(2, "Testing 64-col dual sense amp driver")

        a = dual_sense_amp_array(word_size=64, words_per_row=1)
        self.local_check(a)


TestBase.run_tests(__name__)
