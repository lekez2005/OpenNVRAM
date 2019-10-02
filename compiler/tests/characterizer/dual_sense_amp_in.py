#!/usr/bin/env python3

from char_test_base import CharTestBase


class DualSenseAmpIn(CharTestBase):
    instantiate_dummy = True

    def runTest(self):
        import debug
        from globals import OPTS
        import sys

        sys.path.append("../../modules/bitline_compute")

        OPTS.sense_amp_array = "dual_sense_amp_array"
        OPTS.sense_amp_tap = "dual_sense_amp_tap"
        OPTS.sense_amp = "dual_sense_amp"

        from modules.bitline_compute.dual_sense_amp_array import dual_sense_amp_array

        OPTS.check_lvsdrc = False
        self.run_drc_lvs = False

        cols = 64

        load = dual_sense_amp_array(word_size=cols, words_per_row=1)

        self.load_pex = self.run_pex_extraction(load, "dual_sense_amp")
        self.dut_name = load.name

        self.period = "800ps"

        cap_vals = {}

        for pin in ["en", "en_bar"]:

            dut_instance = "X4 "

            for col in range(cols):
                dut_instance += " bl[{0}] br[{0}] and[{0}] nor[{0}] ".format(col)

            # en pin is just before en_bar pin
            if pin == "en":
                dut_instance += " d d_dummy "
            else:
                dut_instance += " d_dummy d "

            dut_instance += " search_ref vdd gnd sense_amp_array \n"
            dut_instance += "Vsearch_ref search_ref gnd 0.65 \n"

            self.dut_instance = dut_instance

            self.run_optimization()

            with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
                for line in log_file:
                    if line.startswith("Optimization completed"):
                        cap_val = float(line.split()[-1])
                        cap_vals[pin] = cap_val
        for key in cap_vals:
            cap_val = cap_vals[key]
            debug.info(1, "{} Cap  = {:2g}fF".format(key, cap_val*1e15))
            debug.info(1, "{} Cap per sense amp = {:2g}fF".format(key, cap_val*1e15/cols))


DualSenseAmpIn.run_tests(__name__)
