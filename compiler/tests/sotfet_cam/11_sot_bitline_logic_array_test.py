#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""

from cam_test_base import CamTestBase
import debug


class SotBitlineLogicArrayTest(CamTestBase):

    def setUp(self):
        super().setUp()
        import tech
        tech.drc_exceptions["SfBitlineLogicArray"] = tech.drc_exceptions["min_nwell"]

    @staticmethod
    def make_logic_array(word_size):
        from modules.sotfet.sf_bitline_logic_array import SfBitlineLogicArray
        return SfBitlineLogicArray(word_size=word_size)

    def test_8_columns(self):
        debug.info(2, "Testing bitline logic array with columns=8")
        a = self.make_logic_array(word_size=8)
        self.local_check(a)

    def test_16_columns(self):
        debug.info(2, "Testing bitline logic array with columns=16")
        a = self.make_logic_array(word_size=16)
        self.local_check(a)

    def test_64_columns(self):
        debug.info(2, "Testing bitline logic array with columns=64")
        a = self.make_logic_array(word_size=64)
        self.local_check(a)

    def test_256_columns(self):
        debug.info(2, "Testing bitline logic array with columns=256")
        a = self.make_logic_array(word_size=32)
        self.local_check(a)


CamTestBase.run_tests(__name__)
