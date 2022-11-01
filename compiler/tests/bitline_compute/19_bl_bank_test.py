#!/usr/bin/env python

from test_base import TestBase
from bank_test_base import BankTestBase


class BlBankTest(BankTestBase, TestBase):
    def local_check(self, a, final_verification=False):
        from globals import OPTS
        if OPTS.baseline:
            super().local_check(a, final_verification)
            return
        if hasattr(a.decoder_logic, "add_body_taps"):
            a.decoder_logic.add_body_taps()
        TestBase.local_check(self, a, final_verification)


BlBankTest.run_tests(__name__)
