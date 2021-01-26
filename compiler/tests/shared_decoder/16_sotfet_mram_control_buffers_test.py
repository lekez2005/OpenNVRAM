#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class SotfetMramControlBuffersTest(TestBase):
    config_template = "config_shared_sotfet_{}"

    def test_logic_buffers_mirror(self):
        from globals import OPTS
        from modules.shared_decoder.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
        OPTS.mirror_sense_amp = True
        dut = SotfetMramControlBuffers()
        self.local_check(dut)

    def test_logic_buffers_no_mirror(self):
        from globals import OPTS
        from modules.shared_decoder.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
        OPTS.mirror_sense_amp = False
        dut = SotfetMramControlBuffers()
        self.local_check(dut)


SotfetMramControlBuffersTest.run_tests(__name__)
