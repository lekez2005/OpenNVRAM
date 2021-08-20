#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""
from types import SimpleNamespace

from test_base import TestBase


class SotfetMramControlBuffersTest(TestBase):

    def run_with_input_pins(self, input_pins):
        from globals import OPTS
        OPTS.num_banks = 1
        OPTS.create_decoder_clk = True
        # test one row
        OPTS.control_buffers_num_rows = 2

        def get_input_pins():
            return input_pins

        precharge_array = SimpleNamespace(get_input_pins=get_input_pins)
        bank = SimpleNamespace(is_left_bank=False, words_per_row=1,
                               precharge_array=precharge_array)

        from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
        dut = SotfetMramControlBuffers(bank)
        self.local_check(dut)

    # def test_with_enable_only(self):
    #     self.run_with_input_pins(["en"])

    def test_with_bl_br_reset(self):
        self.run_with_input_pins(["bl_reset", "br_reset"])


SotfetMramControlBuffersTest.run_tests(__name__)
