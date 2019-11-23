#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class ControlBuffersTest(TestBase):
    def test_control_buffers(self):
        from modules.control_buffers import ControlBuffers
        a = ControlBuffers()
        self.local_check(a)


TestBase.run_tests(__name__)
