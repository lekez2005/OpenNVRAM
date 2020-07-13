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

        from modules.shared_decoder.cmos_sram import CmosSram
        from sim_steps_generator import SimStepsGenerator

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

        if mode == CMOS_MODE:
            sram_class = CmosSram
        else:
            sram_class = CmosSram

        self.sram = sram_class(word_size=OPTS.word_size, num_words=OPTS.num_words,
                               num_banks=OPTS.num_banks, words_per_row=OPTS.words_per_row,
                               name="sram1")
        self.sram.sp_write(OPTS.spice_file)

        delay = SimStepsGenerator(self.sram, spfile=OPTS.spice_file,
                                  corner=self.corner, initialize=False)

        delay.trimsp = OPTS.trim_netlist = False

        # probe these cols
        if options.energy:
            cols = [OPTS.word_size - 1]
        else:
            points = 5
            spacing = (self.sram.num_cols - 1) / (points - 1)
            cols = [math.floor(i * spacing) for i in range(points)]
        # align cols to nearest col mux
        cols = [int(x / OPTS.words_per_row) * OPTS.words_per_row for x in cols]

        OPTS.probe_cols = list(set(cols))

        OPTS.sense_amp_ref = 0.7

        period = 1
        duty_cycle = 0.5
        sense_trigger_delay = 0.35

        OPTS.verbose_save = options.verbose_save

        delay.period = period
        delay.duty_cycle = duty_cycle
        delay.read_period = period
        delay.write_period = period
        delay.read_duty_cycle = duty_cycle
        delay.write_duty_cycle = duty_cycle
        OPTS.sense_trigger_delay = sense_trigger_delay

        debug.info(1, "Period = {:3g}".format(period))
        debug.info(1, "Duty Cycle = {:3g}".format(duty_cycle))
        debug.info(1, "Trigger delay = {:3g}".format(OPTS.sense_trigger_delay))

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()

        delay.current_time = duty_cycle * period

        delay.initialize_sim_file()

        # probe sram
        for i in range(options.num_banks):
            delay.probe_bank(i)

        bank = 0 if options.num_banks == 1 else 1
        addresses = [0, (options.num_rows * self.sram.words_per_row - 1)]
        banks = [0, 0]

        for i in range(len(addresses)):
            delay.probe_addresses([addresses[i]], banks[i])

        # run extraction and retrieve probes
        delay.run_pex_and_extract()

        # generate simulation steps
        for i in range(len(addresses)):
            delay.test_address(addresses[i], banks[i])

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


def create_arg_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("-R", "--num_rows", default=64, type=int)
    parser.add_argument("-C", "--num_cols", default=64, type=int)
    parser.add_argument("-W", "--word_size", default=DEFAULT_WORD_SIZE, type=int)
    parser.add_argument("-B", "--num_banks", default=1, choices=[1, 2], type=int)
    parser.add_argument("--fixed_buffers", action="store_true")
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--schematic", action="store_true")
    parser.add_argument("--run_drc", action="store_true")
    parser.add_argument("--run_lvs", action="store_true")
    parser.add_argument("--run_pex", action="store_true")
    parser.add_argument("--verbose_save", action="store_true")
    parser.add_argument("--energy", default=None)
    parser.add_argument("-p", "--plot", default=None)
    return parser


def parse_options(parser):
    mode_ = sys.argv[1]
    assert mode_ in [CMOS_MODE, SOT_MODE, SOTFET_MODE]

    options_, other_args = parser.parse_known_args()
    sys.argv = other_args

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

    sim_directory = "{}_r_{}_c_{}{}{}{}".format(mode_, options_.num_rows, options_.num_cols,
                                                word_size_suffix, bank_suffix, schem_suffix)
    openram_temp_ = os.path.join(os.environ["SCRATCH"], "openram", "shared_dec", sim_directory)
    return openram_temp_


CMOS_MODE = "cmos"
SOT_MODE = "sot"
SOTFET_MODE = "sotfet"

DEFAULT_WORD_SIZE = 32

if __name__ == "__main__":
    arg_parser = create_arg_parser()
    mode, options = parse_options(arg_parser)

    SharedDecoderSimulator.run_optimizations = not options.fixed_buffers
    openram_temp = get_sim_directory(options, mode)
    SharedDecoderSimulator.temp_folder = openram_temp

    SharedDecoderSimulator.run_tests(__name__)
