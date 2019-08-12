#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""

from cam_test_base import CamTestBase
import debug


class SotFlopArrayTest(CamTestBase):

    def setUp(self):
        super().setUp()
        import tech
        tech.drc_exceptions["sot_flop_array"] = tech.drc_exceptions["min_nwell"]

    @staticmethod
    def make_flop(word_size):
        from modules.sotfet.sot_flop_array import sot_flop_array
        return sot_flop_array(word_size=word_size)

    def test_8_columns(self):
        debug.info(2, "Testing ms_flop_array for columns=8")
        a = self.make_flop(word_size=8)
        self.local_check(a)

    def test_16_columns(self):
        debug.info(2, "Testing ms_flop_array for columns=16")
        a = self.make_flop(word_size=16)
        self.local_check(a)

    def test_64_columns(self):
        debug.info(2, "Testing ms_flop_array for columns=64")
        a = self.make_flop(word_size=64)
        self.local_check(a)

    def test_256_columns(self):
        debug.info(2, "Testing ms_flop_array for columns=256")
        a = self.make_flop(word_size=256)
        self.local_check(a)


CamTestBase.run_tests(__name__)
