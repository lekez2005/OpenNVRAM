#!/usr/bin/env python3

from char_test_base import CharTestBase


class PrechargeIn(CharTestBase):
    instantiate_dummy = False

    def runTest(self):
        import debug
        from globals import OPTS

        from modules.precharge_array import precharge_array

        OPTS.check_lvsdrc = False
        self.run_drc_lvs = False

        cols = 64

        load = precharge_array(size=4, columns=cols)

        self.load_pex = self.run_pex_extraction(load, "precharge")
        self.dut_name = load.name

        self.period = "800ps"

        dut_instance = "X4 "

        for col in range(cols):
            dut_instance += " bl[{0}] br[{0}] ".format(col)

        dut_instance += " d vdd {} \n".format(load.name)

        self.dut_instance = dut_instance

        self.run_optimization()

        with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
            for line in log_file:
                if line.startswith("Optimization completed"):
                    cap_val = float(line.split()[-1])
                    debug.info(1, "Cap = {:.2g}fF".format(cap_val*1e15))
                    debug.info(1, "Cap per um = {:.2g}fF".format(
                        cap_val*1e15/(load.pc_cell.ptx_width * cols)))


PrechargeIn.run_tests(__name__)
