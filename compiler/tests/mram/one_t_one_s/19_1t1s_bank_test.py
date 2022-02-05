#!/usr/bin/env python3

from one_t_one_s_test_base import TestBase
from bank_test_base import BankTestBase


class MramBankTest(BankTestBase, TestBase):
    pass


MramBankTest.run_tests(__name__)
