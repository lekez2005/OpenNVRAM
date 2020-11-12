#!/usr/bin/env python3
"""
Run a regression test on a flop_array.
"""

from test_base import TestBase
import debug


class WordlineBufferTest(TestBase):

    def test_inverter(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.push_rules.wordline_inverter import wordline_inverter
        a = wordline_inverter(size=4)
        self.local_check(a)

    def test_mirror_inverter(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.push_rules.wordline_inverter import wordline_inverter
        a = wordline_inverter(size=4, mirror=True)
        self.local_check(a)

    def test_buffer(self):
        from globals import OPTS
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.push_rules.wordline_buffer import wordline_buffer
        a = wordline_buffer(OPTS.wordline_buffers)
        self.local_check(a)

    def test_buffer_tap(self):
        from globals import OPTS
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.push_rules.wordline_buffer import wordline_buffer
        from modules.push_rules.wordline_buffer_array import buffer_tap
        buffer = wordline_buffer(OPTS.wordline_buffers)
        tap = buffer_tap(buffer)
        self.local_check(tap)

    def test_buffer_array(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.push_rules.wordline_buffer_array import wordline_buffer_array
        buffer_array = wordline_buffer_array(32)
        self.local_check(buffer_array)


WordlineBufferTest.run_tests(__name__)
