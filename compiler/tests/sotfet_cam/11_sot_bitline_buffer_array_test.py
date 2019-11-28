#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""
from unittest import skipIf

from cam_test_base import CamTestBase


class SotBitlineBufferArrayTest(CamTestBase):

    @skipIf(True, "skip switch")
    def test_standalone_bitline_buffer(self):
        from modules.sotfet.sf_bitline_buffer import SfBitlineBuffer
        from globals import OPTS

        self.debug.info(2, "Testing standalone bitline logic buffer with size [2, 4]")

        OPTS.bitline_buffer_sizes = [2, 4]
        a = SfBitlineBuffer()
        self.local_check(a)

    @skipIf(True, "skip switch")
    def test_standalone_sw_bitline_buffer(self):
        from globals import OPTS
        OPTS.bitcell = "cam_bitcell"

        from modules.sotfet.cmos.sw_bitline_buffer import SwBitlineBuffer

        OPTS.bitline_buffer_sizes = [2, 6]
        a = SwBitlineBuffer()
        self.local_check(a)

    @skipIf(False, "skip switch")
    def test_8_col_array(self):
        from modules.sotfet.sf_bitline_buffer_array import SfBitlineBufferArray
        from globals import OPTS
        self.debug.info(2, "Testing 8-column bitline buffer array")

        OPTS.bitline_buffer_sizes = [2, 4]
        OPTS.bitcell = "cam_bitcell"
        OPTS.bitline_buffer = "sw_bitline_buffer.SwBitlineBuffer"
        OPTS.bitline_buffer_tap = "sw_bitline_buffer.SwBitlineBufferTap"
        a = SfBitlineBufferArray(word_size=32)
        self.local_check(a)


CamTestBase.run_tests(__name__)
