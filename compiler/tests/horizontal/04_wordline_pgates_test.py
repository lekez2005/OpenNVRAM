#!/usr/bin/env python3
"""
Run a regression test on a flop_array.
"""

from test_base import TestBase
import debug


class WordlinePgatesTest(TestBase):

    def test_pnand2(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.pnand2_wordline import pnand2_wordline
        a = pnand2_wordline(size=1)
        self.add_body_tap_and_test(a)

    def test_pnand3(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.pnand2_wordline import pnand3_wordline
        a = pnand3_wordline(size=1)
        self.add_body_tap_and_test(a)

    def test_pnor2(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.pnand2_wordline import pnor2_wordline
        a = pnor2_wordline(size=1)
        self.add_body_tap_and_test(a)

    def test_pnor3(self):
        debug.info(1, "Testing standalone wordline buffer inverter")
        from modules.horizontal.pnand2_wordline import pnor3_wordline
        a = pnor3_wordline(size=1)
        self.add_body_tap_and_test(a)


WordlinePgatesTest.run_tests(__name__)
