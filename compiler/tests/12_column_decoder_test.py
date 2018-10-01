#!/usr/bin/env python2.7
"""
Run a regresion test on a wordline_driver array
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
import debug


class column_decoder_test(openram_test):

    @classmethod
    def setUpClass(cls):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

    @classmethod
    def tearDownClass(cls):
        globals.end_openram()

    def run_commands(self, row_addr_size, col_addr_size):

        global verify
        import verify
        OPTS.check_lvsdrc = False

        import column_decoder

        decoder = column_decoder.ColumnDecoder(row_addr_size=row_addr_size, col_addr_size=col_addr_size)
        self.local_check(decoder)

    def test_no_decoder(self):
        debug.info(1, "Decoder with no column mux")
        self.run_commands(row_addr_size=6, col_addr_size=0)

    def test_1_2_decoder(self):
        debug.info(1, "Decoder with 1->2 column mux")
        self.run_commands(row_addr_size=6, col_addr_size=1)

    def test_2_4_decoder(self):
        debug.info(1, "Decoder with 2->4 column mux")
        self.run_commands(row_addr_size=6, col_addr_size=2)

    def test_3_8_decoder(self):
        debug.info(1, "Decoder with 3->8 column mux")
        self.run_commands(row_addr_size=6, col_addr_size=3)

        
# instantiate a copy of the class to actually run the test
(OPTS, args) = globals.parse_args()
del sys.argv[1:]
header(__file__, OPTS.tech_name)
if __name__ == "__main__":
    unittest.main()
