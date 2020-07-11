#!/usr/bin/env python3

from char_test_base import CharTestBase


class WriteDriverIn(CharTestBase):
    instantiate_dummy = True

    def runTest(self):
        import debug
        from globals import OPTS
        import sys

        sys.path.append("../../modules/bitline_compute")

        OPTS.write_driver = "write_driver_mask"
        OPTS.write_driver_mod = "write_driver_mask_3x"
        OPTS.write_driver_tap = "write_driver_mask_3x_tap"

        from modules.write_driver_mask_array import write_driver_mask_array

        OPTS.check_lvsdrc = False
        self.run_drc_lvs = False

        cols = 64

        self.max_c = 100e-15
        self.min_c = 1e-15
        self.start_c = 0.5 * (self.max_c + self.min_c)

        load = write_driver_mask_array(columns=cols, word_size=cols)

        self.load_pex = self.run_pex_extraction(load, "write_driver")
        self.dut_name = load.name

        self.period = "800ps"

        cap_vals = {}

        for pin in ["en", "en_bar"]:

            dut_instance = "X4 " + " ".join([" vdd gnd "]*cols)

            for col in range(cols):
                dut_instance += " bl[{0}] br[{0}] ".format(col)
            dut_instance += " ".join([" gnd "]*cols)

            # en pin is just before en_bar pin
            if pin == "en":
                dut_instance += " d d_dummy "
            else:
                dut_instance += " d_dummy d "
            dut_instance += " vdd gnd write_driver_mask_array \n"

            self.dut_instance = dut_instance

            self.run_optimization()

            with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
                for line in log_file:
                    if line.startswith("Optimization completed"):
                        cap_val = float(line.split()[-1])
                        cap_vals[pin] = cap_val

        for key in cap_vals:
            cap_val = cap_vals[key]
            debug.info(1, "{} Cap = {:2g}fF".format(key, cap_val*1e15))
            debug.info(1, "{} Cap per write driver = {:2g}fF".format(key, cap_val*1e15/cols))


WriteDriverIn.run_tests(__name__)
