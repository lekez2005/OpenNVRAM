#!/usr/bin/env python

from test_base import TestBase
from sram_test_base import SramTestBase


class BlSramTest(SramTestBase, TestBase):
    pass


BlSramTest.run_tests(__name__)
