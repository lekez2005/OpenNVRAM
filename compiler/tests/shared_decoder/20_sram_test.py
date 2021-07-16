#!/usr/bin/env python3

from sram_test_base import SramTestBase
from test_base import TestBase


class SramTest(SramTestBase, TestBase):
    pass


SramTest.run_tests(__name__)
