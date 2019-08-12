#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from cam_test_base import CamTestBase


class LogicBuffersTest(CamTestBase):
    def test_logic_buffers(self):
        from modules.sotfet.logic_buffers import LogicBuffers
        a = LogicBuffers()
        self.local_check(a)


CamTestBase.run_tests(__name__)
