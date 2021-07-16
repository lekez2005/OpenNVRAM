#!/usr/bin/env python3

from bank_test_base import BankTestBase
from test_base import TestBase


class BankTest(BankTestBase, TestBase):
    pass


BankTest.run_tests(__name__)
