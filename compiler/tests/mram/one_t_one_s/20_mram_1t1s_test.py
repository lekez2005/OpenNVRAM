#!/usr/bin/env python3

from one_t_one_s_test_base import TestBase
from sram_test_base import SramTestBase


class Mram1t1sTest(SramTestBase, TestBase):
    pass


Mram1t1sTest.run_tests(__name__)
