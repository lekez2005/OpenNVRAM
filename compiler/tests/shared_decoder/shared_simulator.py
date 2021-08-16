#!/usr/bin/env python3

from test_base import TestBase

from simulator_base import SimulatorBase

class SharedDecoderSimulator(TestBase):

    def setUp(self):
        super().setUp()

    def get_netlist_gen_class(self):
        from shared_decoder.sim_steps_generator import SimStepsGenerator
        return SimStepsGenerator

    def test_simulation(self):

        import debug
        from globals import OPTS

        self.sram = self.create_sram()
        debug.info(1, "Write netlist to file")
        self.sram.sp_write(OPTS.spice_file)

        netlist_generator = self.create_netlist_generator(self.sram)
        netlist_generator.configure_timing(self.sram)
        if self.cmd_line_opts.energy:
            netlist_generator.write_generic_stimulus()
        else:
            netlist_generator.write_delay_stimulus()
        netlist_generator.stim.run_sim()

        debug.info(1, "Read Period = {:3g}".format(netlist_generator.read_period))
        debug.info(1, "Read Duty Cycle = {:3g}".format(netlist_generator.read_duty_cycle))

        debug.info(1, "Write Period = {:3g}".format(netlist_generator.write_period))
        debug.info(1, "Write Duty Cycle = {:3g}".format(netlist_generator.write_duty_cycle))

        debug.info(1, "Trigger delay = {:3g}".format(OPTS.sense_trigger_delay))
        debug.info(1, "Area = {:.3g} x {:.3g} = {:3g}".format(self.sram.width, self.sram.height,
                                                              self.sram.width * self.sram.height))


if __name__ == "__main__":
    SharedDecoderSimulator.parse_options()
    SharedDecoderSimulator.run_tests(__name__)
