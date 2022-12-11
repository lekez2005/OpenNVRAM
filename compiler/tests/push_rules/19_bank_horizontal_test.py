#!/usr/bin/env python

from test_base import TestBase
from bank_test_base import BankTestBase


class BankTest(BankTestBase, TestBase):
    @staticmethod
    def get_bank_class():
        from modules.push_rules.horizontal_bank import HorizontalBank
        return HorizontalBank, {"adjacent_bank": None}


BankTest.run_tests(__name__)
