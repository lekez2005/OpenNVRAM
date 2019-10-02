#!/usr/bin/env python3

from char_test_base import CharTestBase


class TriStateIn(CharTestBase):
    instantiate_dummy = False

    def runTest(self):
        import debug
        from globals import OPTS

        from modules.bitcell_array import bitcell_array

        OPTS.check_lvsdrc = False
        self.run_drc_lvs = False

        cols = 32
        rows = 32

        load = bitcell_array(cols=cols, rows=rows)

        self.load_pex = self.run_pex_extraction(load, "bitcell_array")
        self.dut_name = load.name

        self.period = "800ps"

        pin_names = ["wl", "bl", "br"]
        for i in range(3):
            pin_name = pin_names[i]
            debug.info(1, "Characterizing pin {}".format(pin_name))
            dut_instance = "X4 "
            for col in range(cols):
                if pin_name == "bl" and col == 0:
                    dut_instance += " d "
                elif col == 0:
                    dut_instance += " vdd "
                else:
                    dut_instance += " gnd ".format(col)
                if pin_name == "br" and col == 0:
                    dut_instance += " d "
                elif col == 0:
                    dut_instance += " vdd "
                else:
                    dut_instance += " br[{0}] ".format(col)
            for row in range(rows):
                if pin_name == "wl" and row == 0:
                    dut_instance += " d "
                elif dut_instance == 0:
                    dut_instance += " vdd "
                else:
                    dut_instance += " gnd ".format(row)

            dut_instance += " vdd gnd {} \n".format(load.name)

            self.dut_instance = dut_instance

            self.run_optimization()

            with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
                for line in log_file:
                    if line.startswith("Optimization completed"):
                        cap_val = float(line.split()[-1])
                        debug.info(1, "Cap = {:2g}fF".format(cap_val * 1e15))
                        if pin_name == "wl":
                            debug.info(1, "Cap per col = {:2g}fF".format(cap_val * 1e15 / rows))
                        else:
                            debug.info(1, "Cap per row = {:2g}fF".format(cap_val * 1e15 / cols))


TriStateIn.run_tests(__name__)
