#!/usr/bin/env python3

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class SenseAmpIn(DistributedLoadMixin, CharTestBase):
    fixed_pins = ["en", "ml[0]"]

    def get_pins(self):
        return ["en", "ml[0]"]

    def get_cell_name(self):
        from globals import OPTS
        return OPTS.search_sense_amp_mod

    def save_result(self, cell_name, pin, *args, **kwargs):
        pin = pin.replace("[0]", "")
        super(SenseAmpIn, self).save_result(cell_name, pin, *args, **kwargs)

    def make_dut(self, num_elements):
        load = self.create_class_from_opts("search_sense_amp_array", rows=num_elements)
        return load

    def get_dut_instance_statement(self, pin):
        from globals import OPTS
        dut_instance = ""

        all_pins = [x for x in self.load.pins]
        if not pin == "vcomp":
            dut_instance += "Vsearch_ref search_ref gnd {} \n".format(OPTS.sense_amp_vref)
            all_pins[all_pins.index("vcomp")] = "search_ref"

        dut_instance += "X4 "

        all_pins[all_pins.index(pin)] = "d"

        dut_instance += " ".join(all_pins)
        dut_instance += f" {self.load.name} \n"

        return dut_instance


SenseAmpIn.run_tests(__name__)
