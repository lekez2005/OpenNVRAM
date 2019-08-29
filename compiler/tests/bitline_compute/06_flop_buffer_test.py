#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class FlopBufferTest(TestBase):
    def test_control_buffers(self):
        from modules.bitline_compute.flop_buffer import FlopBuffer
        import tech
        from globals import OPTS
        tech.drc_exceptions["DecoderLogic"] = tech.drc_exceptions["latchup"]
        a = FlopBuffer(OPTS.control_flop, OPTS.control_buffers)
        self.local_check(a)


TestBase.run_tests(__name__)
