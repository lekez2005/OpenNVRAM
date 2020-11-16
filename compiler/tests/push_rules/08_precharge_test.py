#!/usr/bin/env python3
"""
Run regression tests on a parameterized horizontal precharge
"""
from test_base import TestBase


class PrechargeTest(TestBase):

    def test_small_precharge(self):
        import debug
        from modules.push_rules.precharge_horizontal import precharge_horizontal

        debug.info(2, "Checking 1x size horizontal precharge")

        dut = precharge_horizontal(name="precharge", size=1)
        self.local_check(dut)

    def test_large_precharge(self):
        import debug
        from modules.push_rules.precharge_horizontal import precharge_horizontal

        debug.info(2, "Checking 1x size horizontal precharge")

        dut = precharge_horizontal(name="precharge", size=3.5)
        self.local_check(dut)

    def test_small_precharge_array(self):
        import debug
        from modules.push_rules.precharge_array_horizontal import PrechargeArray

        debug.info(2, "Checking small precharge array")

        dut = PrechargeArray(columns=32)
        self.local_check(dut)

    def test_large_precharge_array(self):
        import debug
        from modules.push_rules.precharge_array_horizontal import PrechargeArray

        debug.info(2, "Checking small precharge array")

        dut = PrechargeArray(columns=256)
        self.local_check(dut)


PrechargeTest.run_tests(__name__)
