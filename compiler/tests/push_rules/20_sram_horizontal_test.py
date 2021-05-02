#!/usr/bin/env python
import os
import sys


parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# insert at beginning of path to override current directory's test_base
sys.path.insert(0, os.path.join(parent_dir, "shared_decoder"))
sram_test = __import__("20_sram_test")


class SramTest(sram_test.SramTest):
    config_template = "config_push_hs_{}"

    def setUp(self):
        super().setUp()
        from globals import OPTS
        OPTS.baseline = True

    @staticmethod
    def get_sram_class():
        from modules.push_rules.horizontal_sram import HorizontalSram
        return HorizontalSram


SramTest.run_tests(__name__)
