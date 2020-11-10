#!/usr/bin/env python3
"""
Run a regression test on a latched control logic module.
"""

from test_base import TestBase


class LatchedControlLogicTest(TestBase):
    def test_control_buffers(self):
        from modules.push_rules.latched_control_logic import LatchedControlLogic
        a = LatchedControlLogic()
        self.local_check(a)


LatchedControlLogicTest.run_tests(__name__)
