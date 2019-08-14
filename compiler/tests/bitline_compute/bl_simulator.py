#!/usr/bin/env python3

import os
import sys

from test_base import TestBase
from globals import OPTS


class Simulator(TestBase):
    baseline = False

    def setUp(self):
        super(Simulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def replace_temp_folder(self, new_temp):
        if not os.path.exists(new_temp):
            os.makedirs(new_temp)
        OPTS.openram_temp = new_temp
        for attr, file_name in [("spice_file", "temp.sp"), ("pex_spice", "pex.sp"),
                                ("reduced_spice", "reduced.sp"), ("gds_file", "temp.gds")]:
            new_val = os.path.join(new_temp, file_name)
            setattr(OPTS, attr, new_val)

    def run_commands(self, use_pex, word_size, num_words):
        folder_name = "baseline" if self.baseline else "compute"
        temp_folder = os.path.join(OPTS.openram_temp, "{}_{}_{}".format(folder_name, word_size, num_words))
        self.replace_temp_folder(temp_folder)

        from modules.bitline_compute.bl_sram import BlSram
        from sim_steps_generator import SimStepsGenerator

        OPTS.use_pex = use_pex

        OPTS.word_size = word_size
        OPTS.num_words = num_words

        sram_class = BlSram

        self.sram = sram_class(word_size=OPTS.word_size, num_words=OPTS.num_words, num_banks=1, name="sram1",
                               words_per_row=OPTS.words_per_row)
        self.sram.sp_write(OPTS.spice_file)

        delay = SimStepsGenerator(self.sram, spfile=OPTS.spice_file, corner=self.corner, initialize=False)

        delay.trimsp = False

        delay.read_period = 2
        delay.write_period = 2
        delay.read_duty_cycle = 0.4
        delay.write_duty_cycle = 0.4

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()

        delay.write_delay_stimulus()

        delay.stim.run_sim()

    def test_schematic(self):
        OPTS.trim_netlist = False
        OPTS.run_drc = False
        OPTS.run_lvs = False
        OPTS.run_pex = False
        OPTS.separate_vdd = True
        self.run_commands(use_pex=False, word_size=32, num_words=32)


if 'baseline' in sys.argv:
    Simulator.baseline = True
    sys.argv.remove('baseline')
else:
    Simulator.baseline = False


TestBase.run_tests(__name__)
