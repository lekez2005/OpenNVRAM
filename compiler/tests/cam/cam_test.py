#!/usr/bin/env python2.7
"""
Run a regresion test on a 1 bank SRAM
"""

from cam_test_base import CamTestBase, run_tests
import debug
from globals import OPTS


class CamTest(CamTestBase):


    def test_single_bank(self):
        from modules.cam import cam

        OPTS.bank_gate_buffers["default"] = [1, 3, 6]
        OPTS.bank_gate_buffers["clk"] = [2, 4, 8]

        debug.info(1, "Single bank, no column mux with control logic")
        a = cam.Cam(word_size=48, num_words=32, num_banks=1, name="sram1")
        self.local_check(a, final_verification=True)


run_tests(__name__)
