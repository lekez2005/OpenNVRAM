#!/usr/bin/env python3

from char_test_base import CharTestBase


class FlopCin(CharTestBase):

    def runTest(self):
        import debug
        from modules.ms_flop_array import ms_flop_array

        cols = 64

        self.max_c = 100e-15
        self.min_c = 1e-15
        self.start_c = 0.5 * (self.max_c + self.min_c)

        load = ms_flop_array(columns=cols, word_size=cols)

        self.load_pex = self.run_pex_extraction(load, "out_buffer")
        self.dut_name = load.name

        self.period = "800ps"

        dut_instance = "X4 " + " ".join(["din[{}]".format(x) for x in range(cols)])
        for col in range(cols):
            dut_instance += " dout[{0}] dout_bar[{0}] ".format(col)
        dut_instance += " d vdd gnd flop_array_c{0}_w{0}".format(cols)

        self.dut_instance = dut_instance

        self.run_optimization()

        with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
            for line in log_file:
                if line.startswith("Optimization completed"):
                    cap_val = float(line.split()[-1])
                    debug.info(1, "Cap = {:2g}fF".format(cap_val*1e15))
                    debug.info(1, "Cap per flop = {:2g}fF".format(cap_val*1e15/cols))


FlopCin.run_tests(__name__)
