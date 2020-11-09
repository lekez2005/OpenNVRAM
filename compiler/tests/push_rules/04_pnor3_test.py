#!/usr/bin/env python3
"""
Run regression tests on a parameterized horizontal nor2
"""
from test_base import TestBase


class Pnor2Test(TestBase):

    def test_size_1(self):
        import debug
        from modules.push_rules.pnor3_horizontal import pnor3_horizontal

        debug.info(2, "Checking 1x size horizontal nor2")
        dut = pnor3_horizontal(size=1)
        self.add_body_tap_and_test(dut)

    def test_size_2(self):
        import debug
        from modules.push_rules.pnor3_horizontal import pnor3_horizontal

        debug.info(2, "Checking two-finger horizontal nor2")
        dut = pnor3_horizontal(size=2)
        self.add_body_tap_and_test(dut)


Pnor2Test.run_tests(__name__)
