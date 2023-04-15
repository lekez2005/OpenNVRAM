#!/usr/bin/env python3

from test_base import TestBase
from sram_test_base import SramTestBase



class SramTest(SramTestBase, TestBase):
    pass


SramTest.run_tests(__name__)
