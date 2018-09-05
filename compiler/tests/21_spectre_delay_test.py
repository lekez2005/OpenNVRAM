#!/usr/bin/env python2.7
"""
Run a regresion test on various srams
"""

import sys,os
import unittest



from testutils import header, openram_test

sys.path.append(os.path.join(sys.path[0],".."))

import globals
from globals import OPTS


class timing_sram_test(openram_test):

    def setUp(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

        import sram
        OPTS.check_lvsdrc = False
        self.sram = sram.sram(word_size=OPTS.word_size,
                              num_words=OPTS.num_words,
                              num_banks=OPTS.num_banks,
                              name="sram1")
        zero_address = 0
        mid_address = self.sram.num_rows / 2 - 1  # first bank
        max_address = self.sram.num_words - 1

        # addresses = [zero_address, mid_address, max_address]
        self.addresses = [zero_address]

        import tech
        self.loads = [tech.spice["msflop_in_cap"] * 4]
        self.slews = [tech.spice["rise_time"] * 2]


    def tearDown(self):
        globals.end_openram()

    def test_schematic_simulation(self):
        use_pex = False
        from functional_test import FunctionalTest
        func_test = FunctionalTest(self.sram, spice_name="spectre", use_pex=use_pex)

        func_test.add_probes(self.addresses)
        func_test.run_drc_lvs_pex()
        func_test.create_delay(self.corner)

        delay = func_test.delay
        delay.analyze(delay.probe_address, delay.probe_data, self.slews, self.loads)

    @unittest.skip("Skipping extracted simulation test")
    def test_extracted_simulation(self):
        use_pex = True
        from functional_test import FunctionalTest
        func_test = FunctionalTest(self.sram, spice_name="spectre", use_pex=use_pex)

        func_test.add_probes(self.addresses)
        func_test.run_drc_lvs_pex()
        func_test.create_delay(self.corner)

        delay = func_test.delay
        delay.analyze(delay.probe_address, delay.probe_data, self.slews, self.loads)


# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
