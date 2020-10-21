#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from cam_test_base import CamTestBase


class FastControlBuffersTest(CamTestBase):
    def test_logic_buffers(self):
        from modules.sotfet.fast_ramp.fast_ramp_control_buffers import FastRampControlBuffers
        a = FastRampControlBuffers()
        self.local_check(a)


CamTestBase.run_tests(__name__)
