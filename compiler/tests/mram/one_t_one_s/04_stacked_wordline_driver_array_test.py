#!/usr/bin/env python3

from one_t_one_s_test_base import TestBase


class StackedWordlineDriverArrayTest(TestBase):

    def test_stacked_wwl_driver(self):
        from globals import OPTS

        self.debug.info(2, "Testing 16-row wwl_driver array")
        dut = self.create_class_from_opts("wwl_driver", name="wwl_driver",
                                          rows=16, buffer_stages=OPTS.wwl_buffers)
        dut.add_body_taps()
        self.local_check(dut)

    def test_stacked_rwl_driver(self):
        from globals import OPTS
        self.debug.info(2, "Testing 16-row rwl_driver array")
        dut = self.create_class_from_opts("rwl_driver", name="rwl_driver",
                                          rows=16, buffer_stages=OPTS.rwl_buffers)
        dut.add_body_taps()
        self.local_check(dut)


StackedWordlineDriverArrayTest.run_tests(__name__)
