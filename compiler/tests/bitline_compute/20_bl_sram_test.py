#!/usr/bin/env python

from test_base import TestBase
from sram_test_base import SramTestBase


class BlSramTest(SramTestBase, TestBase):
    def get_sram_class(self):
        from globals import OPTS
        OPTS.configure_modules(None, OPTS)
        sram_class = self.load_class_from_opts("sram_class")
        return sram_class


BlSramTest.run_tests(__name__)
