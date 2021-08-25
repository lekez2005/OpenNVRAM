#!/usr/bin/env python3
"""
Run a delay test on cam using spice simulator
"""
from cam_simulator import CamSimulator
from cam_test_base import CamTestBase


class CamSimulationTest(CamSimulator, CamTestBase):
    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def test_simulation(self):
        self.run_simulation()

    def print_sim_information(self, netlist_generator):
        from globals import OPTS
        import debug

        debug.info(1, "Write Period = {:3g}".format(netlist_generator.write_period))
        debug.info(1, "Write Duty Cycle = {:3g}".format(netlist_generator.write_duty_cycle))

        debug.info(1, "Search Period = {:3g}".format(netlist_generator.search_period))
        debug.info(1, "Search Duty Cycle = {:3g}".format(netlist_generator.search_duty_cycle))

        debug.info(1, "Trigger delay = {:3g}".format(OPTS.sense_trigger_delay))
        area = self.sram.width * self.sram.height
        debug.info(1, "Area = {:.3g} x {:.3g} = {:3g}".format(self.sram.width, self.sram.height,
                                                              area))


if __name__ == "__main__":
    CamSimulationTest.parse_options()
    CamSimulationTest.run_tests(__name__)
