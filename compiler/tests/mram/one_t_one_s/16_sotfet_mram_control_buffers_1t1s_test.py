#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""
from types import SimpleNamespace

from one_t_one_s_test_base import TestBase


class SotfetMramControlBuffersTest(TestBase):

    def test_logic_buffers_no_mirror(self):
        from globals import OPTS
        OPTS.num_banks = 1
        OPTS.create_decoder_clk = True
        OPTS.control_buffers_num_rows = 2
        driver_array = SimpleNamespace(pins=["en"])

        bank = SimpleNamespace(is_left_bank=False, words_per_row=1,
                               write_driver_array=driver_array,
                               sense_amp_array=driver_array,
                               tri_gate_array=driver_array)

        from modules.mram.one_t_one_s.sotfet_mram_control_buffers_1t1s \
            import SotfetMramControlBuffers1t1s
        dut = SotfetMramControlBuffers1t1s(bank)
        self.local_check(dut)


SotfetMramControlBuffersTest.run_tests(__name__)
