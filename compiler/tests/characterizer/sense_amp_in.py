#!/usr/bin/env python3
import sys
from importlib import reload

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class SenseAmpIn(DistributedLoadMixin, CharTestBase):

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--sense_amp_array", default="sense_amp_array")
        cls.parser.add_argument("--sense_amp", default="sense_amp")
        cls.parser.add_argument("--sense_amp_tap", default="sense_amp_tap")
        cls.parser.add_argument("--search_ref", default=0.7, type=float)

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.sense_amp_array = self.options.sense_amp_array
        OPTS.sense_amp = self.options.sense_amp
        OPTS.sense_amp_tap = self.options.sense_amp_tap

    def get_cell_name(self):
        from globals import OPTS
        return OPTS.sense_amp

    def make_dut(self, num_elements):
        from globals import OPTS

        if OPTS.sense_amp_array == "dual_sense_amp_array":
            sys.path.append("../../modules/bitline_compute")

        module = reload(__import__(OPTS.sense_amp_array))
        mod_class = getattr(module, OPTS.sense_amp_array)
        load = mod_class(word_size=num_elements, words_per_row=1)
        return load

    def get_dut_instance_statement(self, pin):
        dut_instance = "X4 "
        cols = self.load.original_dut.word_size

        if self.options.sense_amp == "dual_sense_amp":
            for col in range(cols):
                dut_instance += " bl[{0}] br[{0}] and[{0}] nor[{0}] ".format(col)

            # en pin is just before en_bar pin
            if pin == "en":
                dut_instance += " d d_dummy "
            else:
                dut_instance += " d_dummy d "
            dut_instance += " search_ref vdd gnd {} \n".format(self.load.name)
            dut_instance += "Vsearch_ref search_ref gnd {} \n".format(self.options.search_ref)
        else:
            for col in range(cols):
                dut_instance += " bl[{0}] br[{0}] data[{0}] ".format(col)

            if self.options.sense_amp == "sense_amp":
                # en pin is just before en_bar pin
                if pin == "en":
                    dut_instance += " d d_dummy "
                else:
                    dut_instance += " d_dummy d "
            elif self.options.sense_amp_array == "latched_sense_amp_array":
                pin_order = ["en", "preb", "sampleb"]
                pin_sub = ["d" if x == pin else x + "_dummy" for x in pin_order]
                dut_instance += " {} ".format(" ".join(pin_sub))

            dut_instance += " vdd gnd {} \n".format(self.load.name)
        return dut_instance

    def get_pins(self):
        if self.options.sense_amp in ["sense_amp", "dual_sense_amp"]:
            return ["en", "en_bar"]
        elif self.options.sense_amp_array == "latched_sense_amp_array":
            return ["en", "preb", "sampleb"]


SenseAmpIn.run_tests(__name__)
