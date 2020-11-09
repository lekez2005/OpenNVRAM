#!/usr/bin/env python3
"""
Run a regression test on a hierarchical_decoder.
"""
import os
from importlib import reload

from test_base import TestBase
import debug

period_32_rows = 100e-12
setup_time = 50e-12
rise_time = 5e-12


class HorizontalRowDecoderTest(TestBase):

    def test_row_32(self):
        for row in [32, 64, 128, 256, 512]:
            self.run_for_rows(row)
        # self.run_for_rows(32)

    # def test_row_64(self):
    #     self.run_for_rows(64)
    #
    # def test_row_128(self):
    #     self.run_for_rows(128)
    #
    # def test_row_256(self):
    #     self.run_for_rows(256)
    #
    # def test_row_512(self):
    #     self.run_for_rows(512)

    def run_for_rows(self, num_rows):
        from modules.push_rules.horizontal_row_decoder import horizontal_row_decoder
        debug.info(1, "Testing {} row sample for hierarchical_decoder".format(num_rows))

        a = horizontal_row_decoder(rows=num_rows)
        # self.local_check(a)
        self.run_sim(a)

    def run_sim(self, dut: 'hierarchical_decoder'):
        import characterizer
        reload(characterizer)
        from characterizer import stimuli

        vdd_value = self.corner[1]

        num_rows = dut.rows
        num_address_bits = dut.num_inputs
        period = (num_rows / 32) * period_32_rows

        sim_length = period * (1 + num_rows)

        control = ""
        control += "Vdd vdd gnd {}\n".format(vdd_value)
        control += "Vclk clk gnd pulse 0 {0} {1} {2} {2} '0.5*{3}' {3}\n".format(vdd_value, -setup_time,
                                                                                 rise_time, period)
        a_pins = ' '.join(["A[{}]".format(x) for x in range(num_address_bits)])
        decode_pins = ' '.join(["decode[{}]".format(x) for x in range(num_rows)])
        en_pin = ""

        control += "Xdut {} {} {} clk vdd gnd {}\n".format(a_pins, decode_pins, en_pin, dut.name)
        # Address
        for i in range(num_address_bits):
            control += "VA{0} A[{0}] gnd pulse {1} 0 0 {2} {2} '0.5*{3}' {3}\n".format(i, vdd_value,
                                                                                       rise_time,
                                                                                       (2 ** (i + 1)) * period)
        vec_file_name = self.temp_file("expect.vec")
        with open(vec_file_name, "w") as vec_file:
            vec_file.write("TUNIT ns\n")
            vec_file.write("VOH {}\n".format(0.5 * vdd_value))
            vec_file.write("VOL {}\n".format(0.5 * vdd_value))
            vec_file.write("RADIX {}\n".format(' '.join(["1"] * num_rows)))
            vec_file.write("IO {}\n".format(' '.join(["O"] * num_rows)))
            vec_file.write("VNAME {}\n".format(' '.join(["decode[{}]".format(x) for x in range(num_rows)])))
            # Expected output
            for i in range(num_rows):
                t = (setup_time + (i + 1) * period) * 1e9

                output = [0] * num_rows
                output[i] = 1

                vec_file.write("{:.5g} {}\n".format(t, " ".join(map(str, output))))

        control += ".vec '{}'\n".format(vec_file_name)

        self.stim_file_name = self.temp_file("stim.sp")
        dut_file = self.temp_file("dut.sp")
        dut.sp_write(dut_file)

        with open(self.stim_file_name, "w") as stim_file:
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(dut_file)
            stim_file.write(control)
            stim.write_control(sim_length / 1e-9)

        stim.run_sim()
        with open(self.temp_file("stim_tran.vecerr"), "r") as results_f:
            results = results_f.read()
            if results:
                print(results)
                self.fail("Vector check mismatch for rows {}".format(num_rows))


TestBase.run_tests(__name__)
