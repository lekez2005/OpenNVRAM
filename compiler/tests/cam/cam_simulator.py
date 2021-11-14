from simulator_base import SimulatorBase


class CamSimulator(SimulatorBase):
    config_template = "config_cam_{}"
    sim_dir_suffix = "cam"
    valid_modes = ["cmos"]

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

    def get_netlist_gen_class(self):
        from modules.cam.cam_spice_characterizer import CamSpiceCharacterizer
        return CamSpiceCharacterizer
