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

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        from functional_test import FunctionalTest

        corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

        func_test = FunctionalTest(spice_name="spectre", use_pex=False)

        zero_address = 0
        mid_address = func_test.sram.num_rows / 2 - 1  # first bank
        max_address = func_test.sram.num_words - 1

        # addresses = [zero_address, mid_address, max_address]
        addresses = [zero_address]


        func_test.add_probes(addresses)
        func_test.run_drc_lvs_pex()
        func_test.create_delay(corner)

        delay = func_test.delay

        #delay.find_feasible_period()

        import tech
        loads = [tech.spice["msflop_in_cap"]*4]
        slews = [tech.spice["rise_time"]*2]
        delay.analyze(delay.probe_address, delay.probe_data, slews, loads)

        globals.end_openram()

# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
