#!/usr/bin/env python3

from cam_test_base import CamTestBase
from sram_test_base import SramTestBase


class CamTest(SramTestBase, CamTestBase):
    pass


CamTest.run_tests(__name__)
