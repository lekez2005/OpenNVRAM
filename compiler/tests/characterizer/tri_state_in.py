#!/usr/bin/env python3
from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class TriStateIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True

    def get_pins(self):
        return ["en", "en_bar"]

    def get_cell_name(self):
        from globals import OPTS
        return OPTS.tri_gate

    def make_dut(self, num_elements):
        from modules.tri_gate_array import tri_gate_array
        load = tri_gate_array(columns=num_elements, word_size=num_elements)
        return load

    def get_dut_instance_statement(self, pin):
        cols = self.load.original_dut.word_size

        dut_instance = "X4 "

        for col in range(cols):
            dut_instance += " in[{0}] ".format(col)
        for col in range(cols):
            dut_instance += " out[{0}] ".format(col)

        # en pin is just before en_bar pin
        if pin == "en":
            dut_instance += " d d_dummy "
        else:
            dut_instance += " d_dummy d "

        dut_instance += " vdd gnd {} \n".format(self.load.name)
        return dut_instance


TriStateIn.run_tests(__name__)
