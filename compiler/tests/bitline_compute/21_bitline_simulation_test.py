#!/usr/bin/env python3
"""
Run a delay test on bitline compute using spectre/hspice
"""

from test_base import TestBase
from bl_simulator import BlSimulator


class BitlineSimulationTest(BlSimulator, TestBase):

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def test_simulation(self):
        self.run_simulation()


if __name__ == "__main__":
    BitlineSimulationTest.parse_options()
    BitlineSimulationTest.run_tests(__name__)
