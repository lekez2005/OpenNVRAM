#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from cam_test_base import CamTestBase


class LogicBuffersTest(CamTestBase):
    def test_logic_buffers(self):
        from modules.sotfet.cmos.sw_logic_buffers import SwLogicBuffers
        a = SwLogicBuffers()
        self.local_check(a)


CamTestBase.run_tests(__name__)