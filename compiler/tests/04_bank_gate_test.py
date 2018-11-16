
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


class bank_gate_test(openram_test):

    @classmethod
    def setUpClass(cls):
        globals.init_openram("config_20_{0}".format(OPTS.tech_name))

    @classmethod
    def tearDownClass(cls):
        globals.end_openram()


    def test_bank_gate(self):
        debug.info(1, "Checking bank gate")

        global verify
        import verify
        OPTS.check_lvsdrc = False

        from bank_gate import BankGate
        from bank_gate import ControlGate
        control_gates = [
            ControlGate("s_en"),
            ControlGate("clk", route_complement=True),
            ControlGate("w_en")
        ]

        gate = BankGate(control_gates)
        self.local_check(gate)

    def test_left_output(self):
        debug.info(1, "Checking bank gate")

        global verify
        import verify
        OPTS.check_lvsdrc = False

        from bank_gate import BankGate
        from bank_gate import ControlGate
        control_gates = [
            ControlGate("s_en"),
            ControlGate("clk", route_complement=True, output_dir="left"),
            ControlGate("sig2", route_complement=False, output_dir="left"),
            ControlGate("w_en")
        ]

        gate = BankGate(control_gates)
        self.local_check(gate)

        
# instantiate a copy of the class to actually run the test
(OPTS, args) = globals.parse_args()
del sys.argv[1:]
header(__file__, OPTS.tech_name)
if __name__ == "__main__":
    unittest.main()
