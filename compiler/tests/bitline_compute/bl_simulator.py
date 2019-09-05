#!/usr/bin/env python3

import os
import sys

from test_base import TestBase
from globals import OPTS


class BlSimulator(TestBase):
    baseline = False

    def setUp(self):
        super(BlSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def run_commands(self, use_pex, word_size, num_words):

        from modules.bitline_compute.bl_sram import BlSram
        from modules.bitline_compute.baseline.bl_baseline_sram import BlBaselineSram
        from sim_steps_generator import SimStepsGenerator

        OPTS.use_pex = use_pex

        OPTS.word_size = word_size
        OPTS.num_words = num_words

        if self.baseline:
            OPTS.sense_amp = "sense_amp"
            OPTS.sense_amp_tap = "sense_amp_tap"
            OPTS.sense_amp_array = "sense_amp_array"
            OPTS.baseline = True
            sram_class = BlBaselineSram
        else:
            OPTS.baseline = False
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
        OPTS.separate_vdd = False
        self.run_commands(use_pex=True, word_size=word_size, num_words=num_words)


if 'baseline' in sys.argv:
    BlSimulator.baseline = True
    sys.argv.remove('baseline')
else:
    BlSimulator.baseline = False

word_size = 32
num_words = 32
folder_name = "baseline" if BlSimulator.baseline else "compute"
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bl_sram")
temp_folder = os.path.join(openram_temp, "{}_{}_{}".format(folder_name, word_size, num_words))
BlSimulator.temp_folder = temp_folder

BlSimulator.run_tests(__name__)
