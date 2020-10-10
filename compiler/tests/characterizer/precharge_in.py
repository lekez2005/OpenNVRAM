#!/usr/bin/env python3
from importlib import reload

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class PrechargeIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = False

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--size", default=4, type=int)
        cls.parser.add_argument("--precharge", default="precharge")
        cls.parser.add_argument("--precharge_array", default="precharge_array")

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.precharge = self.options.precharge
        OPTS.precharge_array = self.options.precharge_array

    def get_cell_name(self) -> str:
        from globals import OPTS
        bitcell_name = self.load_module_from_str(OPTS.bitcell)().name
        return OPTS.precharge + "_" + bitcell_name

    def get_pins(self):
        return ["en"]

    def make_dut(self, num_elements):
        mod_class = self.load_module_from_str(self.options.precharge_array)
        load = mod_class(size=self.options.size, columns=num_elements)
        return load

    def get_dut_instance_statement(self, pin):
        cols = self.load.original_dut.columns

        dut_instance = "X4 "

        for col in range(cols):
            dut_instance += " bl[{0}] br[{0}] ".format(col)

        dut_instance += " d vdd {} \n".format(self.load.name)
        return dut_instance


PrechargeIn.run_tests(__name__)
