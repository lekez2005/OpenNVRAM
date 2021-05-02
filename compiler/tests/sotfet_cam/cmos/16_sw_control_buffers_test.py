#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from cam_test_base import CamTestBase


class SwControlBuffersTest(CamTestBase):
    def test_logic_buffers(self):
        from modules.sotfet.cmos.sw_control_buffers import SwControlBuffers
        a = SwControlBuffers()
        self.local_check(a)


CamTestBase.run_tests(__name__)
