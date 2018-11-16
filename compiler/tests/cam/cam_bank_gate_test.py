#!/usr/bin/env python2.7

from cam_test_base import CamTestBase, run_tests


class CamBankGateTest(CamTestBase):

    def test_block(self):
        from modules.bank_gate import ControlGate
        from modules.cam.cam_bank_gate import CamBankGate
        control_gates = [

            # left
            ControlGate("s_en", route_complement=True, output_dir="left"),
            ControlGate("search_en", output_dir="left"),
            ControlGate("w_en", output_dir="left"),
            ControlGate("latch_tags", output_dir="left"),
            ControlGate("matchline_chb", output_dir="left"),

            # right
            ControlGate("mw_en", route_complement=True),
            ControlGate("sel_all", route_complement=True),
            ControlGate("clk", route_complement=True)  # to buffer the clk
        ]

        gate = CamBankGate(control_gates)
        self.local_check(gate)


run_tests(__name__)
