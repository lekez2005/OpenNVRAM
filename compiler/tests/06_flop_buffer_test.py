#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from testutils import OpenRamTest


class FlopBufferTest(OpenRamTest):
    def test_control_buffers(self):
        from modules.flop_buffer import FlopBuffer
        import tech
        from globals import OPTS
        tech.drc_exceptions["DecoderLogic"] = tech.drc_exceptions["latchup"]
        a = FlopBuffer(OPTS.control_flop, [6])
        self.local_check(a)


OpenRamTest.run_tests(__name__)
