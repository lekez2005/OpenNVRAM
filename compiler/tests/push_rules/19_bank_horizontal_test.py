#!/usr/bin/env python
import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# insert at beginning of path to override current directory's test_base
sys.path.insert(0, os.path.join(parent_dir, "shared_decoder"))
bank_test = __import__("19_bank_test")


class BankTest(bank_test.BankTest):
    config_template = "config_push_hs_{}"

    def setUp(self):
        super().setUp()
        from globals import OPTS
        OPTS.baseline = True

    @staticmethod
    def get_bank_class():
        from modules.push_rules.horizontal_bank import HorizontalBank
        return HorizontalBank, {"adjacent_bank": None}


BankTest.run_tests(__name__)
