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
import debug

class timing_sram_test(openram_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

        import characterizer
        from characterizer import delay
        import debug

        import sram
        import verify


        OPTS.spice_name="spectre"
        OPTS.analytical_delay = False


        # This is a hack to reload the characterizer __init__ with the spice version
        reload(characterizer)

        debug.info(1, "Testing timing for sample {}, {} words SRAM with {} bank".format(
            OPTS.word_size, OPTS.num_words, OPTS.num_banks))

        OPTS.check_lvsdrc = False
        s = sram.sram(word_size=OPTS.word_size,
                      num_words=OPTS.num_words,
                      num_banks=OPTS.num_banks,
                      name="sram1")

        spice_file = OPTS.spice_file
        s.sp_write(spice_file)

        gds_file = OPTS.gds_file
        s.gds_write(gds_file)

        OPTS.check_lvsdrc = True
        OPTS.use_pex = True
        reload(verify)

        errors = verify.run_pex(s.name, gds_file,
                       spice_file, output=OPTS.pex_spice)
        debug.check(errors == 0, errors)



        probe_address = "1" * s.addr_size
        probe_data = s.word_size - 1
        debug.info(1, "Probe address {0} probe data {1}".format(probe_address, probe_data))

        corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        d = delay.delay(s,spice_file,corner)
        import tech
        loads = [tech.spice["msflop_in_cap"]*4]
        slews = [tech.spice["rise_time"]*2]
        data = d.analyze(probe_address, probe_data,slews,loads)

        globals.end_openram()

# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
