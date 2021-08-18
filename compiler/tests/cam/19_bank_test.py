#!/usr/bin/env python3


from cam_test_base import CamTestBase
from bank_test_base import BankTestBase


class CamBankTest(BankTestBase, CamTestBase):
    pass


CamBankTest.run_tests(__name__)
