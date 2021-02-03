#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class ControlBuffersTest(TestBase):

    def test_control_buffers(self):
        from modules.baseline_latched_control_buffers import LatchedControlBuffers
        a = LatchedControlBuffers(None)
        self.local_check(a)


ControlBuffersTest.run_tests(__name__)
