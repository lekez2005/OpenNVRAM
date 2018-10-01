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


class signal_gate_test(openram_test):

    @classmethod
    def setUpClass(cls):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

    @classmethod
    def tearDownClass(cls):
        globals.end_openram()

    def run_commands(self, buffer_stages):

        global verify
        import verify
        OPTS.check_lvsdrc = False

        import signal_gate

        gate = signal_gate.SignalGate(buffer_stages)
        self.local_check(gate)

    def test_no_buffer(self):
        debug.info(1, "Checking without buffer")
        self.run_commands([1])

    def test_with_odd_buffers(self):
        debug.info(1, "Checking with two buffers")
        self.run_commands([1, 2, 4])

    def test_with_even_buffers(self):
        debug.info(1, "Checking with two buffers")
        self.run_commands([1, 2, 4, 8])

        
# instantiate a copy of the class to actually run the test
(OPTS, args) = globals.parse_args()
del sys.argv[1:]
header(__file__, OPTS.tech_name)
if __name__ == "__main__":
    unittest.main()
