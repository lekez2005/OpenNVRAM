#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""
from types import SimpleNamespace

from test_base import TestBase


class SotfetMramControlBuffersTest(TestBase):
    config_template = "config_shared_sotfet_{}"

    def test_logic_buffers_no_mirror(self):
        from globals import OPTS
        OPTS.num_banks = 1
        OPTS.create_decoder_clk = True
        # test one row
        OPTS.control_buffers_num_rows = 2
        bank = SimpleNamespace(is_left_bank=False, words_per_row=1)

        from modules.shared_decoder.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
        dut = SotfetMramControlBuffers(bank)
        self.local_check(dut)


SotfetMramControlBuffersTest.run_tests(__name__)
