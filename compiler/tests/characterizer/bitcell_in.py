#!/usr/bin/env python3

import shutil

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class BitcellIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True
    num_rows = num_cols = 1

    def save_result(self, cell_name, pin, *args, **kwargs):
        pin = pin.replace("[0]", "")
        super(BitcellIn, self).save_result(cell_name, pin, *args, **kwargs)

    def get_size_suffixes(self, num_elements):
        if self.dut_pin == "bl[0]":
            return [("rows", num_elements), ("wire", self.load.wire_length)]
        else:
            return [("cols", num_elements), ("wire", self.load.wire_length)]
        

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--bitcell", default="bitcell")
        cls.parser.add_argument("--bitcell_array", default="bitcell_array")
        cls.parser.add_argument("--bitcell_tap", default="body_tap")

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.bitcell = self.options.bitcell
        OPTS.bitcell_array = self.options.bitcell_array
        OPTS.body_tap = self.options.bitcell_tap

    def get_cell_name(self) -> str:
        from globals import OPTS
        return self.load_module_from_str(OPTS.bitcell)().name

    def get_pins(self):
        return ["bl[0]", "wl[0]"]

    def make_dut(self, num_elements):
        bitcell_array_class = self.load_module_from_str(self.options.bitcell_array)

        pin = self.dut_pin
        if pin == "bl[0]":
            self.num_rows = num_elements
            self.num_cols = 1
        else:
            self.num_rows = 1
            self.num_cols = num_elements

        name = "bitcell_array_r{}_c{}".format(self.num_rows, self.num_cols)
        load = bitcell_array_class(cols=self.num_cols, rows=self.num_rows,
                                  name=name)
        return load

    def get_dut_instance_statement(self, pin) -> str:
        cols = self.num_cols
        rows = self.num_rows

        dut_instance = "X4 "

        # bit-lines
        if "bl" in pin:
            dut_instance += " d d_dummy "
        else:
            # connect all bitlines to vdd
            for col in range(cols):
                dut_instance += " vdd vdd "

        # word-lines
        if "wl" in pin:
            dut_instance += " d "
        # connect word-lines to gnd
        else:
            for row in range(rows):
                dut_instance += " gnd "

        dut_instance += " vdd gnd {} \n".format(self.load.name)

        return dut_instance


BitcellIn.run_tests(__name__)
