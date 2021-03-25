#!/usr/bin/env python3
"""
Run a regression test on a hierarchical_decoder.
"""

from test_base import TestBase
import row_decoder_base_test
import debug

row_decoder_base_test.setup_time = 50e-12


class RowDecoderTest(row_decoder_base_test.RowDecoderBase, TestBase):

    def run_for_rows(self, num_rows):
        debug.info(1, "Testing {} row sample for hierarchical_decoder".format(num_rows))
        dut, dut_statement = self.instantiate_dut(num_rows)
        self.local_check(dut)
        # self.run_sim(dut, dut_statement)

    @staticmethod
    def instantiate_dut(num_rows):
        from modules.horizontal.row_decoder_horizontal import row_decoder_horizontal

        dut = row_decoder_horizontal(rows=num_rows)
        a_pins = ' '.join(["A[{}]".format(x) for x in range(dut.num_inputs)])
        decode_pins = ' '.join(["decode[{}]".format(x) for x in range(dut.rows)])

        return dut, "Xdut {} {} clk vdd gnd {}\n".format(a_pins, decode_pins, dut.name)


RowDecoderTest.run_tests(__name__)
