#!/usr/bin/env python2.7
"""
Run a regresion test on a 4 bank SRAM
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug

class sram_4bank_test(openram_test):

    def runTest(self):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))
        global verify
        import verify
        OPTS.check_lvsdrc = False

        import sram

        debug.info(1, "Four bank, no column mux with control logic")
        a = sram.sram(word_size=32, num_words=128, num_banks=4, name="sram1")
        self.local_check(a, final_verification=True)

        debug.info(1, "Four bank two way column mux with control logic")
        a = sram.sram(word_size=32, num_words=256, num_banks=4, name="sram2")
        self.local_check(a, final_verification=True)

        debug.info(1, "Four bank, four way column mux with control logic")
        a = sram.sram(word_size=32, num_words=512, num_banks=4, name="sram3")
        self.local_check(a, final_verification=True)

        # debug.info(1, "Four bank, eight way column mux with control logic")
        # a = sram.sram(word_size=2, num_words=256, num_banks=4, name="sram4")
        # self.local_check(a, final_verification=True)

        OPTS.check_lvsdrc = True
        globals.end_openram()
        
# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
