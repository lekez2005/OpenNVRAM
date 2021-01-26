#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class ControlBuffersTest(TestBase):

    def test_control_buffers(self):
        from modules.baseline_latched_control_buffers import LatchedControlBuffers
        a = LatchedControlBuffers()
        self.local_check(a)

    def test_control_buffers_no_mux(self):
        from modules.shared_decoder.control_buffers_no_col_mux import LatchedControlBuffers
        a = LatchedControlBuffers()
        self.local_check(a)


ControlBuffersTest.run_tests(__name__)
