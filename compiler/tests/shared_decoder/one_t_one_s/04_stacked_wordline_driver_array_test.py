#!/usr/bin/env python3
import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(parent_dir))

from test_base import TestBase


class StackedWordlineDriverArrayTest(TestBase):

    def test_stacked_wwl_driver(self):
        import debug

        debug.info(2, "Testing 16-row wwl_driver array")
        dut = self.create_class_from_opts("wwl_driver", name="wwl_driver",
                                          rows=16, buffer_stages=[2, 4, 8])
        dut.add_body_taps()
        self.local_check(dut)

    def test_stacked_rwl_driver(self):
        import debug

        debug.info(2, "Testing 16-row rwl_driver array")
        dut = self.create_class_from_opts("rwl_driver", name="rwl_driver",
                                          rows=16, buffer_stages=[2, 4, 8])
        dut.add_body_taps()
        self.local_check(dut)


StackedWordlineDriverArrayTest.run_tests(__name__)
