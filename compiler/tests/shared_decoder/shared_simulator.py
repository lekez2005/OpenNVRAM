#!/usr/bin/env python3

import argparse
import math
import os
import sys

from test_base import TestBase
from globals import OPTS


class SharedDecoderSimulator(TestBase):

    def setUp(self):
        super().setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def test_simulation(self):

        import debug

        from sim_steps_generator import SimStepsGenerator
        from base import utils

        OPTS.use_pex = not options.schematic
        OPTS.run_drc = options.run_drc
        OPTS.run_lvs = options.run_lvs
        OPTS.run_pex = options.run_pex

        OPTS.num_banks = options.num_banks
        OPTS.word_size = options.word_size
        OPTS.words_per_row = int(options.num_cols / options.word_size)
        OPTS.num_words = OPTS.words_per_row * options.num_rows * options.num_banks

        OPTS.run_optimizations = not options.fixed_buffers
        OPTS.energy = options.energy

        setattr(OPTS, "push", getattr(OPTS, "push", False))

        two_bank_push = OPTS.push and options.num_banks == 2

        if options.energy:
            OPTS.pex_spice = OPTS.pex_spice.replace("_energy", "")

        OPTS.pex_spice = OPTS.pex_spice.replace(custom_suffix, "")

        if mode == CMOS_MODE:
            from modules.shared_decoder.cmos_sram import CmosSram
            sram_class = CmosSram
        elif mode == PUSH_MODE:
            from modules.push_rules.horizontal_sram import HorizontalSram
            sram_class = HorizontalSram
        else:
            from modules.shared_decoder.sotfet.sotfet_mram import SotfetMram
            OPTS.configure_sense_amp(not options.latched, OPTS)
            sram_class = SotfetMram

        self.sram = sram_class(word_size=OPTS.word_size, num_words=OPTS.num_words,
                               num_banks=OPTS.num_banks, words_per_row=OPTS.words_per_row,
                               name="sram1")
        debug.info(1, "Write netlist to file")
        self.sram.sp_write(OPTS.spice_file)

        if two_bank_push:
            # words span both banks so having two banks doesn't increase address space
            self.sram.addr_size -= 1

        delay = SimStepsGenerator(self.sram, spfile=OPTS.spice_file,
                                  corner=self.corner, initialize=False)

        delay.trimsp = OPTS.trim_netlist = False

        # probe these cols
        if options.energy:
            cols = [OPTS.word_size - 1]
        else:
            points = 5
            spacing = (options.num_cols - 1) / (points - 1)
            cols = [math.floor(i * spacing) for i in range(points)]
        # align cols to nearest col mux
        cols = [int(x / OPTS.words_per_row) * OPTS.words_per_row for x in cols]

        OPTS.probe_cols = list(sorted(set(cols)))

        first_read, first_write, second_read, second_write = OPTS.configure_timing(options, self.sram,
                                                                                   OPTS)

        delay.write_period = first_write + second_write
        delay.write_duty_cycle = first_write / delay.write_period
        delay.read_period = first_read + second_read
        delay.read_duty_cycle = first_read / delay.read_period

        delay.period = delay.read_period
        delay.duty_cycle = delay.read_duty_cycle

        OPTS.verbose_save = options.verbose_save

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()
        if options.schematic:
            delay.replace_models(delay.sim_sp_file)

        delay.current_time = delay.duty_cycle * delay.period

        delay.initialize_sim_file()
        if two_bank_push:
            self.sram.num_banks = 1  # to trick decode address

        addresses = banks = []
        dummy_address = 1

        if OPTS.energy:
            delay.probe.probe_clk_buf(bank=0)
            delay.probe.probe_address(address=0)
        else:
            # probe sram
            for i in range(options.num_banks):
                delay.probe_bank(i)

            max_bank = 0 if options.num_banks == 1 else 1
            max_bank = 0 if two_bank_push else max_bank
            addresses = [(options.num_rows * self.sram.words_per_row - 1), 0]
            banks = [0, max_bank]

            if not OPTS.baseline and not OPTS.push:
                delay.probe_addresses([dummy_address], 0)

            for i in range(len(addresses)):
                delay.probe_addresses([addresses[i]], banks[i])

        # run extraction and retrieve probes
        if not OPTS.run_drc:
            utils.to_cadence(OPTS.gds_file)
        delay.run_pex_and_extract()

        if two_bank_push:
            self.sram.num_words = int(self.sram.num_words / 2)
            delay.word_size = self.sram.word_size
        delay.initialize_sram(delay.probe, existing_data={})

        if OPTS.energy:
            # minimize saved data to make simulation faster
            OPTS.spectre_save = "selected"
            delay.generate_energy_stimulus()
            delay.probe.current_probes = ["Vvdd:p", "read"]
            delay.probe.saved_nodes = []
            delay.dout_probes = delay.mask_probes = {}
        else:
            for i in range(len(addresses)):
                delay.test_address(addresses[i], banks[i], dummy_address=dummy_address)

        delay.finalize_sim_file()

        def dump_obj(x, f):
            for key in sorted(dir(x)):
                if type(getattr(x, key)).__name__ in ["str", "list", "int", "float"]:
                    f.write("{} = {}\n".format(key, getattr(x, key)))

        with open(os.path.join(OPTS.openram_temp, "config.py"), "w") as config_file:
            dump_obj(OPTS, config_file)
            config_file.write("\n\n")
            dump_obj(delay, config_file)

        delay.stim.run_sim()

        debug.info(1, "Read Period = {:3g}".format(delay.read_period))
        debug.info(1, "Read Duty Cycle = {:3g}".format(delay.read_duty_cycle))

        debug.info(1, "Write Period = {:3g}".format(delay.write_period))
        debug.info(1, "Write Duty Cycle = {:3g}".format(delay.write_duty_cycle))

        debug.info(1, "Trigger delay = {:3g}".format(OPTS.sense_trigger_delay))
        debug.info(1, "Area = {:.3g} x {:.3g} = {:3g}".format(self.sram.width, self.sram.height,
                                                              self.sram.width * self.sram.height))


def create_arg_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("-R", "--num_rows", default=64, type=int)
    parser.add_argument("-C", "--num_cols", default=64, type=int)
    parser.add_argument("-W", "--word_size", default=DEFAULT_WORD_SIZE, type=int)
    parser.add_argument("-B", "--num_banks", default=1, choices=[1, 2], type=int)
    parser.add_argument("-t", "--tech", dest="tech_name", help="Technology name", default="freepdk45")
    parser.add_argument("--fixed_buffers", action="store_true")
    parser.add_argument("--latched", action="store_true")
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--schematic", action="store_true")
    parser.add_argument("--run_drc", action="store_true")
    parser.add_argument("--run_lvs", action="store_true")
    parser.add_argument("--run_pex", action="store_true")
    parser.add_argument("--verbose_save", action="store_true")
    parser.add_argument("--skip_write_check", action="store_true")
    parser.add_argument("--skip_read_check", action="store_true")
    parser.add_argument("--energy", default=None, type=int)
    parser.add_argument("-p", "--plot", default=None)
    parser.add_argument("-o", "--analysis_op_index", default=None, type=int, help="which of the ops to analyze")
    parser.add_argument("-b", "--analysis_bit_index", default=None, type=int, help="what bit to analyze and plot")
    return parser


def parse_options(parser):
    mode_ = sys.argv[1]
    assert mode_ in [CMOS_MODE, SOT_MODE, SOTFET_MODE, PUSH_MODE]

    options_, other_args = parser.parse_known_args()
    sys.argv = other_args + ["-t", options_.tech_name]

    if options_.small:
        options_.num_rows = 64
        options_.num_cols = 64
    elif options_.large:
        options_.num_rows = 128
        options_.num_cols = 256

    assert options_.num_cols % options_.word_size == 0, "Number of columns should be multiple of word size"

    return mode_, options_


def get_sim_directory(options_, mode_):
    bank_suffix = "_bank2" if options_.num_banks == 2 else ""
    if not options_.word_size == DEFAULT_WORD_SIZE:
        word_size_suffix = "_w{}".format(options_.word_size)
    else:
        word_size_suffix = ""
    schem_suffix = "_schem" if options_.schematic else ""

    energy_suffix = "_energy" if options_.energy else ""

    latched_suffix = "_latched" if options_.latched and not mode == CMOS_MODE else ""

    sim_directory = "{}_r_{}_c_{}{}{}{}{}{}".format(mode_, options_.num_rows, options_.num_cols,
                                                    word_size_suffix, bank_suffix, latched_suffix,
                                                    schem_suffix, energy_suffix)
    openram_temp_ = os.path.join(os.environ["SCRATCH"], "openram", "shared_dec",
                                 options_.tech_name,
                                 sim_directory)
    return openram_temp_


CMOS_MODE = "cmos"
SOT_MODE = "sot"
SOTFET_MODE = "sotfet"
PUSH_MODE = "push"

DEFAULT_WORD_SIZE = 32

if __name__ == "__main__":
    arg_parser = create_arg_parser()
    mode, options = parse_options(arg_parser)

    SharedDecoderSimulator.run_optimizations = not options.fixed_buffers
    # custom_suffix = "_03_09"
    custom_suffix = ""
    openram_temp = get_sim_directory(options, mode) + custom_suffix
    SharedDecoderSimulator.temp_folder = openram_temp

    os.environ["OPENRAM_SUBPROCESS_NICE"] = "15"

    SharedDecoderSimulator.run_tests(__name__)
