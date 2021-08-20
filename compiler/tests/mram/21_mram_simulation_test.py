#!/usr/bin/env python3
"""
Run a delay test on mram using spectre/hspice
"""

from test_base import TestBase
from mram_simulator import MramSimulator


class MramSimulationTest(MramSimulator, TestBase):

    def setUp(self):
        super().setUp()
        from globals import OPTS
        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        self.update_global_opts()

    def test_simulation(self):
        self.run_simulation()


if __name__ == "__main__":
    MramSimulationTest.parse_options()
    MramSimulationTest.run_tests(__name__)
