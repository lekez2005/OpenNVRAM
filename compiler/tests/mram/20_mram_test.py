#!/usr/bin/env python3

from test_base import TestBase
from sram_test_base import SramTestBase


class MramTest(SramTestBase, TestBase):
    pass


MramTest.run_tests(__name__)
