#!/usr/bin/env python3
"""
Run regression tests on a parameterized inverter for push rule inverters
"""
from test_base import TestBase


class Pnand2Test(TestBase):

    def test_size_1(self):
        import debug
        from modules.push_rules.pnand2_horizontal import pnand2_horizontal

        debug.info(2, "Checking 1x size horizontal nand2")
        dut = pnand2_horizontal(size=1)
        self.add_body_tap_and_test(dut)

    def test_size_2(self):
        import debug
        from modules.push_rules.pnand2_horizontal import pnand2_horizontal

        debug.info(2, "Checking two-finger horizontal nand2")
        inv = pnand2_horizontal(size=2)
        self.add_body_tap_and_test(inv)


Pnand2Test.run_tests(__name__)
