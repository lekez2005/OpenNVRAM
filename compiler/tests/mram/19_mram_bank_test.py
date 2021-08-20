#!/usr/bin/env python3

from test_base import TestBase
from bank_test_base import BankTestBase


class MramBankTest(BankTestBase, TestBase):
    pass


MramBankTest.run_tests(__name__)
