#!/usr/bin/env python3
"""
Run a regression test on a flop_array.
"""

from test_base import TestBase
import debug


class WordlineBufferTest(TestBase):

    def test_inverter(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.pinv_wordline import pinv_wordline
        a = pinv_wordline(size=4)
        self.add_body_tap_and_test(a)

    def test_mirror_inverter(self):
        debug.info(1, "Testing standalone mirrored wordline buffer inverter")
        from modules.horizontal.pinv_wordline import pinv_wordline
        a = pinv_wordline(size=4, mirror=True)
        self.add_body_tap_and_test(a)

    def test_buffer(self):
        from globals import OPTS
        debug.info(1, "Testing standalone wordline buffer stages")
        from modules.horizontal.wordline_buffer import WordlineBuffer
        a = WordlineBuffer(OPTS.wordline_buffers, route_outputs=False)
        self.add_body_tap_and_test(a)

    def test_logic_buffer(self):
        from globals import OPTS
        debug.info(1, "Testing standalone wordline buffer stages")
        from modules.horizontal.wordline_logic_buffer import WordlineLogicBuffer
        a = WordlineLogicBuffer(OPTS.wordline_buffers, route_outputs=False)
        self.add_body_tap_and_test(a)

    def test_buffer_array(self):
        from  globals import OPTS
        debug.info(1, "Testing wordline buffer array")
        from modules.horizontal.wordline_buffer_array import wordline_buffer_array
        buffer_array = wordline_buffer_array(32, OPTS.wordline_buffers)
        self.local_check(buffer_array)

    def test_buffer_no_enable_array(self):
        from  globals import OPTS
        debug.info(1, "Testing wordline buffer array")
        from modules.horizontal.wordline_buffer_no_enable_array import wordline_buffer_no_enable_array
        buffer_array = wordline_buffer_no_enable_array(32, OPTS.wordline_buffers)
        self.local_check(buffer_array)


WordlineBufferTest.run_tests(__name__)
