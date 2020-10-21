#!/usr/bin/env python3
"""
Run a regression test on a precharge array
"""

from test_base import TestBase
import debug


class PrechargeTest(TestBase):

    def test_single_precharge(self):
        from modules.shared_decoder.sotfet.sotfet_mram_precharge import sotfet_mram_precharge

        debug.info(2, "Checking Sotfet mram precharge")
        pc = sotfet_mram_precharge("sotfet_precharge", size=2)
        self.local_check(pc)


PrechargeTest.run_tests(__name__)
