#!/usr/bin/env python2.7
"""
Run a regresion test on various srams
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class timing_sram_test(openram_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        OPTS.check_lvsdrc = False
        OPTS.spice_name="spectre"
        OPTS.analytical_delay = False

        # This is a hack to reload the characterizer __init__ with the spice version
        import characterizer
        reload(characterizer)
        from characterizer import delay
        if not OPTS.spice_exe:
            debug.error("Could not find {} simulator.".format(OPTS.spice_name),-1)

        import sram
        import tech
        debug.info(1, "Testing timing for sample 1bit, 16words SRAM with 1 bank")
        s = sram.sram(word_size=OPTS.word_size,
                      num_words=OPTS.num_words,
                      num_banks=OPTS.num_banks,
                      name="sram1")

        tempspice = OPTS.openram_temp + "temp.sp"
        s.sp_write(tempspice)

        probe_address = "1" * s.addr_size
        probe_data = s.word_size - 1
        debug.info(1, "Probe address {0} probe data {1}".format(probe_address, probe_data))

        corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        d = delay.delay(s,tempspice,corner)
        import tech
        loads = [tech.spice["msflop_in_cap"]*4]
        slews = [tech.spice["rise_time"]*2]
        data = d.analyze(probe_address, probe_data,slews,loads)
        #print data
        if OPTS.tech_name == "freepdk45":
            golden_data = {'leakage_power': 0.0007348262,
                           'delay_lh': [0.05799613],
                           'read0_power': [0.0384102],
                           'read1_power': [0.03279848],
                           'write1_power': [0.03693655],
                           'write0_power': [0.02717752],
                           'slew_hl': [0.03607912],
                           'min_period': 0.742,
                           'delay_hl': [0.3929995],
                           'slew_lh': [0.02160862]}
        elif OPTS.tech_name == "scn3me_subm":
            golden_data = {'leakage_power': 0.00142014,
                           'delay_lh': [0.8018421],
                           'read0_power': [11.44908],
                           'read1_power': [11.416549999999999],
                           'write1_power': [11.718020000000001],
                           'write0_power': [8.250219],
                           'slew_hl': [0.8273725],
                           'min_period': 2.734,
                           'delay_hl': [1.085861],
                           'slew_lh': [0.5730144]}
        else:
            self.assertTrue(False) # other techs fail

        # Check if no too many or too few results
        self.assertTrue(len(data.keys())==len(golden_data.keys()))
        # Check each result
        for k in data.keys():
            if type(data[k])==list:
                for i in range(len(data[k])):
                    self.isclose(data[k][i],golden_data[k][i],0.15)
            else:
                self.isclose(data[k],golden_data[k],0.15)

        # reset these options
        OPTS.check_lvsdrc = True
        OPTS.spice_name="hspice"
        OPTS.analytical_delay = True
        reload(characterizer)

        globals.end_openram()

# instantiate a copdsay of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
