#!/usr/bin/env python3
"""
Run regression tests on a parameterized horizontal flop buffer
"""
from test_base import TestBase


class FlopBufferTest(TestBase):

    def test_single_stage(self):
        import debug
        from globals import OPTS

        debug.info(2, "Checking 1 stage flop buffer")

        from modules.horizontal.flop_buffer_horizontal import FlopBufferHorizontal
        dut = FlopBufferHorizontal(flop_module_name=OPTS.control_flop, buffer_stages=[1])
        self.local_check(dut)

    def test_single_stage_no_top_dummy(self):
        import debug
        from globals import OPTS

        debug.info(2, "Checking 1 stage no top dummy flop buffer")

        from modules.horizontal.flop_buffer_horizontal import FlopBufferHorizontal
        dut = FlopBufferHorizontal(flop_module_name=OPTS.control_flop, buffer_stages=[1],
                                   dummy_indices=[0])
        self.local_check(dut)

    def test_double_stage(self):
        import debug
        from globals import OPTS

        debug.info(2, "Checking 2 stage flop buffer")

        from modules.horizontal.flop_buffer_horizontal import FlopBufferHorizontal
        dut = FlopBufferHorizontal(flop_module_name=OPTS.control_flop, buffer_stages=[2, 4])
        self.local_check(dut)


FlopBufferTest.run_tests(__name__)
