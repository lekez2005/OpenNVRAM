#!/usr/bin/env python3

from test_base import TestBase
import debug


class PrechargeResetTest(TestBase):

    def test_min_size(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.precharge_and_reset import PrechargeAndReset
        a = PrechargeAndReset(name="precharge_reset", size=1)
        self.local_check(a)

    def test_large_size(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.precharge_and_reset import PrechargeAndReset
        a = PrechargeAndReset(name="precharge_reset", size=8)
        self.local_check(a)

    def test_mirror(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.precharge_and_reset import PrechargeAndReset
        a = PrechargeAndReset(name="precharge_reset", size=8, mirror=True)
        self.local_check(a)

    def test_precharge_reset_array(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.precharge_reset_array import PrechargeResetArray
        a = PrechargeResetArray(columns=32, size=8)
        self.local_check(a)


PrechargeResetTest.run_tests(__name__)
