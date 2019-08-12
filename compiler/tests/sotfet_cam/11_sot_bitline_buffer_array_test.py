#!/usr/bin/env python3
"""
Run a regression test on a dff_array.
"""

from cam_test_base import CamTestBase


class SotBitlineBufferArrayTest(CamTestBase):

    def test_standalone_bitline_buffer(self):
        from modules.sotfet.sf_bitline_buffer import SfBitlineBuffer
        from globals import OPTS
        import tech

        self.debug.info(2, "Testing standalone bitline logic buffer with size [2, 4]")

        tech.drc_exceptions["SfBitlineBuffer"] = tech.drc_exceptions["latchup"] + ["PO.W.19__PO.S.43"]

        OPTS.bitline_buffer_sizes = [2, 4]
        a = SfBitlineBuffer()
        self.local_check(a)

    def test_8_col_array(self):
        from modules.sotfet.sf_bitline_buffer_array import SfBitlineBufferArray
        from globals import OPTS
        self.debug.info(2, "Testing 8-column bitline buffer array")

        OPTS.bitline_buffer_sizes = [2, 4]
        a = SfBitlineBufferArray(word_size=32)
        self.local_drc_check(a)


CamTestBase.run_tests(__name__)
