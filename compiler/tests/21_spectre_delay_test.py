#!/usr/bin/env python3
"""
Run a delay test on sram using spectre
"""

from unittest import skipIf, skip

from testutils import OpenRamTest
from globals import OPTS

OPTS.spice_name = "spectre"
OPTS.analytical_delay = False
OpenRamTest.initialize_tests()

from functional_test import FunctionalTest


@skipIf(not OPTS.spice_exe, "spectre not found")
class TimingSramTest(OpenRamTest):

    def setup_sram(self):
        import sram
        import tech

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

        self.sram = sram.sram(word_size=OPTS.word_size,
                              num_words=OPTS.num_words,
                              words_per_row=OPTS.words_per_row,
                              num_banks=OPTS.num_banks,
                              name="sram1")
        self.sram.sp_write(OPTS.spice_file)
        zero_address = 0
        mid_address = int(self.sram.num_rows / 2) - 1  # first bank
        max_address = self.sram.num_words - 1

        self.addresses = [zero_address, mid_address, max_address]
        # self.addresses = [zero_address]

        self.loads = [tech.spice["msflop_in_cap"] * 4]
        self.slews = [tech.spice["rise_time"] * 2]

    def run_simulation(self, use_pex=False):
        func_test = FunctionalTest(self.sram, spice_name="spectre", use_pex=use_pex)
        func_test.add_probes(self.addresses)
        if use_pex:
            func_test.run_drc_lvs_pex()

        func_test.create_delay(self.corner)

        delay = func_test.delay
        delay.run_delay_simulation()
        delay.analyze(delay.probe_address, delay.probe_data, self.slews, self.loads)

    # @unittest.skip("Skipping simulation test")
    def test_schematic_simulation(self):
        self.setup_sram()
        self.run_simulation(use_pex=False)

    @skip("Skipping extracted test")
    def test_extracted_simulation(self):
        self.setup_sram()
        self.run_simulation(use_pex=True)


OpenRamTest.run_tests(__name__)
