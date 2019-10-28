#!/usr/bin/env python3

import os
import sys

from test_base import TestBase
from globals import OPTS


class BlSimulator(TestBase):
    baseline = False
    run_optimizations = True
    serial = False
    energy_sim = False

    def setUp(self):
        super(BlSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def run_commands(self, use_pex, word_size, num_words):

        from modules.bitline_compute.bl_sram import BlSram
        from modules.bitline_compute.bs_sram import BsSram
        from modules.bitline_compute.baseline.baseline_sram import BaselineSram
        from energy_steps_generator import EnergyStepsGenerator
        from sim_steps_generator import SimStepsGenerator

        OPTS.use_pex = use_pex

        OPTS.word_size = word_size
        OPTS.num_words = num_words
        OPTS.words_per_row = 1

        OPTS.run_optimizations = self.run_optimizations

        OPTS.serial = self.serial

        if self.serial:
            sram_class = BsSram
        elif OPTS.baseline:
            sram_class = BaselineSram
        else:
            sram_class = BlSram

        self.sram = sram_class(word_size=OPTS.word_size, num_words=OPTS.num_words, num_banks=1, name="sram1",
                               words_per_row=OPTS.words_per_row)
        self.sram.sp_write(OPTS.spice_file)

        OPTS.pex_submodules = [self.sram.bank]

        # TODO you can define custom steps generators here following the pattern in EnergyStepsGenerator
        if OPTS.energy_sim:
            delay = EnergyStepsGenerator(self.sram, spfile=OPTS.spice_file, corner=self.corner, initialize=False)
        else:
            delay = SimStepsGenerator(self.sram, spfile=OPTS.spice_file, corner=self.corner, initialize=False)

        delay.trimsp = False

        OPTS.sense_trigger_delay = 0.6

        delay.read_period = 2.2
        delay.write_period = 2.2
        delay.read_duty_cycle = 0.4
        delay.write_duty_cycle = 0.4

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()

        delay.write_delay_stimulus()

        delay.stim.run_sim()

    def test_schematic(self):
        use_pex = False
        OPTS.trim_netlist = False
        OPTS.run_drc = False
        OPTS.run_lvs = False
        OPTS.run_pex = False

        OPTS.top_level_pex = True

        OPTS.separate_vdd = False

        OPTS.energy_sim = BlSimulator.energy_sim

        self.run_commands(use_pex=use_pex, word_size=word_size, num_words=num_words)


if 'fixed_buffers' in sys.argv:
    BlSimulator.run_optimizations = False
    sys.argv.remove('fixed_buffers')
else:
    BlSimulator.run_optimizations = False  # for now just always use the hand-tuned values

force_bit_serial = False  # just to make testing easier
word_size = 32
num_words = 32

if "serial" in sys.argv or force_bit_serial:
    force_bit_serial = True
    folder_name = "serial"
elif "baseline" in sys.argv:
    folder_name = "baseline"
else:
    folder_name = "compute"

for arg in sys.argv:
    if "energy=" in arg:
        BlSimulator.energy_sim = arg[7:]

BlSimulator.serial = force_bit_serial

openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bl_sram")

temp_folder = os.path.join(openram_temp, "{}_{}_{}".format(folder_name, word_size, num_words))
if not BlSimulator.run_optimizations:
    temp_folder += "_fixed3"
BlSimulator.temp_folder = temp_folder

BlSimulator.run_tests(__name__)
