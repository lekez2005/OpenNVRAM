#!/usr/bin/env python3
from importlib import reload

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class WriteDriverIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.write_driver = self.options.write_driver
        OPTS.write_driver_mod = self.options.write_driver_mod
        OPTS.write_driver_tap = self.options.write_driver_tap

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--write_driver_array", default="write_driver_array")
        cls.parser.add_argument("--write_driver", default="write_driver")
        cls.parser.add_argument("--write_driver_mod", default="write_driver")
        cls.parser.add_argument("--write_driver_tap", default="write_driver_tap")

    def get_cell_name(self):
        from globals import OPTS
        return OPTS.write_driver_mod

    def get_pins(self):
        if self.options.write_driver == "write_driver":
            return ["en"]
        elif self.options.write_driver == "write_driver_mask":
            return ["en", "en_bar"]

    def make_dut(self, num_elements):

        mod_class = self.load_module_from_str(self.options.write_driver_array)
        load = mod_class(columns=num_elements, word_size=num_elements)
        return load

    def get_dut_instance_statement(self, pin):

        cols = self.load.original_dut.word_size

        dut_instance = "X4 " + " ".join([" vdd gnd "] * cols)

        for col in range(cols):
            dut_instance += " bl[{0}] br[{0}] ".format(col)
        dut_instance += " ".join([" gnd "] * cols)

        if self.options.write_driver == "write_driver":
            dut_instance += " d "
        else:
            # en pin is just before en_bar pin
            if pin == "en":
                dut_instance += " d d_dummy "
            else:
                dut_instance += " d_dummy d "

        dut_instance += " vdd gnd {} \n".format(self.load.name)
        return dut_instance


WriteDriverIn.run_tests(__name__)
