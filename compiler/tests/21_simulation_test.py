#!/usr/bin/env python3
"""
Run a delay test on sram using spectre/hspice
"""

from simulator_base import SimulatorBase
from testutils import OpenRamTest


class SimulationTest(OpenRamTest, SimulatorBase):

    def setUp(self):
        super().setUp()
        from globals import OPTS
        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        self.update_global_opts()

    def get_netlist_gen_class(self):
        from characterizer import SpiceCharacterizer
        return SpiceCharacterizer

    def test_simulation(self):
        self.run_simulation()


SimulationTest.parse_options()
SimulationTest.run_tests(__name__)
