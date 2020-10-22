#!/usr/bin/env python
import argparse
import os
import sys

from cam_test_base import CamTestBase
from globals import OPTS


class CamSimulator(CamTestBase):
    cmos = False

    def setUp(self):
        self.cmos = mode == CMOS_MODE
        super(CamSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def test_simulation(self):

        import debug
        from base import utils

        from sf_cam_delay import SfCamDelay
        from sf_cam_dut import SfCamDut

        OPTS.use_pex = not options.schematic

        OPTS.trim_netlist = False
        OPTS.run_drc = options.run_drc
        OPTS.run_lvs = options.run_lvs
        OPTS.run_pex = options.run_pex
        OPTS.separate_vdd = False
        OPTS.verbose_save = options.verbose_save
        OPTS.slow_ramp = options.slow_ramp
        OPTS.series = options.series
        OPTS.use_ultrasim = options.use_ultrasim

        OPTS.energy = options.energy

        OPTS.word_size = options.num_cols
        OPTS.num_words = options.num_rows
        OPTS.words_per_row = 1

        SfCamDut.is_sotfet = mode == SOTFET_MODE

        if options.series:
            device_mode = "OR"
        else:
            device_mode = "AND"

        if self.cmos:
            from modules.sotfet.cmos.sw_cam import SwCam
            cam_class = SwCam
        else:
            OPTS.configure_sotfet_params(device_mode)
            if options.slow_ramp:
                from modules.sotfet.sf_cam import SfCam
                cam_class = SfCam
            else:
                from modules.sotfet.fast_ramp.sf_fast_ramp_cam import SfFastRampCam
                cam_class = SfFastRampCam

        self.cam = cam_class(word_size=OPTS.word_size, num_words=OPTS.num_words,
                             num_banks=1, name="sram1",
                             words_per_row=OPTS.words_per_row)
        self.cam.sp_write(OPTS.spice_file)

        if not OPTS.run_drc:
            utils.to_cadence(OPTS.gds_file)

        delay = SfCamDelay(self.cam, spfile=OPTS.spice_file, corner=self.corner, initialize=False)

        delay.trimsp = False

        num_rows = self.cam.bank.num_rows
        num_cols = self.cam.bank.num_cols

        if self.cmos:
            if num_rows == 32:
                first_write = 0.2
                second_write = 0.2
                first_search = 0.2
                second_search = 0.25
            elif num_rows == 64:
                first_write = 0.3
                second_write = 0.25
                first_search = 0.3
                second_search = 0.3
            else:
                first_write = 0.4
                second_write = 0.3
                first_search = 0.5
                second_search = 0.4
        else:
            if OPTS.slow_ramp:
                first_write = 0.6 * 2.5
                second_write = 0.4 * 2.5
                first_search = 0.4
                second_search = 0.6
            else:
                if num_rows == 32:
                    first_write = 0.1
                    second_write = 0.45
                    first_search = 0.2
                    second_search = 0.3
                elif num_rows == 64:
                    first_write = 0.25
                    second_write = 0.55
                    if options.series:
                        first_search = 0.25
                        second_search = 1.25
                    else:
                        first_search = 0.25
                        second_search = 0.35

                    if options.series:
                        first_search = 0.4
                        second_search = 1.6
                    else:
                        first_search = 0.4
                        second_search = 0.6

                else:
                    first_write = 0.3
                    second_write = 0.9
                    if options.series:
                        first_search = 0.5
                        second_search = 2
                    else:
                        first_search = 0.5
                        second_search = 0.5

        delay.search_period = first_search + second_search
        delay.search_duty_cycle = first_search / delay.search_period

        delay.write_period = first_write + second_write
        delay.write_duty_cycle = first_write / delay.write_period

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        if options.energy:
            OPTS.pex_spice = OPTS.pex_spice.replace("_energy", "")

        OPTS.pex_spice = OPTS.pex_spice.replace(ultrasim_suffix, "")

        delay.prepare_netlist()

        delay.initialize_sim_file()

        if options.energy:
            OPTS.spectre_save = "selected"

            delay.probe_addresses([])

            delay.generate_energy_steps()
            delay.probe.saved_nodes = []
            delay.saved_currents = ["Vvdd:p", "search"]
        else:
            delay.generate_steps()

        delay.finalize_sim_file()

        delay.stim.run_sim()

        debug.info(1, "Search Period = {:3g}".format(delay.search_period))
        debug.info(1, "Search Duty Cycle = {:3g}".format(delay.search_duty_cycle))

        debug.info(1, "Write Period = {:3g}".format(delay.write_period))
        debug.info(1, "Write Duty Cycle = {:3g}".format(delay.write_duty_cycle))

        debug.info(1, "Area = {:.3g} x {:.3g} = {:3g}".format(self.cam.width, self.cam.height,
                                                              self.cam.width * self.cam.height))


def create_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-R", "--num_rows", default=64, type=int)
    parser.add_argument("-C", "--num_cols", default=64, type=int)
    parser.add_argument("--series", action="store_true")
    parser.add_argument("--slow_ramp", action="store_true")
    parser.add_argument("--optimize", action="store_true")

    parser.add_argument("--run_drc", action="store_true")
    parser.add_argument("--run_lvs", action="store_true")
    parser.add_argument("--run_pex", action="store_true")
    parser.add_argument("--schematic", action="store_true")
    parser.add_argument("--use_ultrasim", action="store_true")
    parser.add_argument("--verbose_save", action="store_true")
    parser.add_argument("--energy", default=None, type=int)
    parser.add_argument("-p", "--plot", default=None)
    return parser


def parse_options(parser):
    first_arg = sys.argv[0]
    mode_ = sys.argv[1]
    assert mode_ in [CMOS_MODE, SOTFET_MODE]

    options_, other_args = parser.parse_known_args()
    sys.argv = [first_arg] + other_args
    return mode_, options_


def get_sim_directory(options_, mode_):
    global ultrasim_suffix

    schem_suffix = "_schem" if options_.schematic else ""
    series_suffix = "_series" if options_.series else ""
    slow_ramp_suffix = "_ramp" if options_.slow_ramp else ""

    energy_suffix = "_energy" if options_.energy else ""

    ultrasim_suffix = "_usim" if options.use_ultrasim else ""

    sim_directory = "{}_r_{}_c_{}{}{}{}{}{}".format(mode_, options_.num_rows, options_.num_cols,
                                                    slow_ramp_suffix, series_suffix, schem_suffix,
                                                    energy_suffix, ultrasim_suffix)
    openram_temp_ = os.path.join(os.environ["SCRATCH"], "openram", "sotfet_cam", sim_directory)
    return openram_temp_


CMOS_MODE = "cmos"
SOTFET_MODE = "sotfet"

ultrasim_suffix = ""

if __name__ == "__main__":
    arg_parser = create_arg_parser()
    mode, options = parse_options(arg_parser)
    openram_temp = get_sim_directory(options, mode)
    CamSimulator.temp_folder = openram_temp

    os.environ["OPENRAM_SUBPROCESS_NICE"] = "15"

    if mode == SOTFET_MODE and not options.slow_ramp:
        CamSimulator.config_template = "config_fast_cam_{}"

    CamSimulator.run_tests(__name__)
