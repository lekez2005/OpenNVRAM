#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class SotfetMramControlBuffersTest(TestBase):
    def test_logic_buffers(self):
        from modules.shared_decoder.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
        dut = SotfetMramControlBuffers()
        self.local_check(dut)


SotfetMramControlBuffersTest.run_tests(__name__)
