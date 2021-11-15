#!/usr/bin/env python3
from importlib import reload

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class WriteDriverIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True
    fixed_pins = ["data[0]", "data_bar[0]", "mask[0]", "mask_bar[0]"]

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def save_result(self, cell_name, pin, *args, **kwargs):
        pin = pin.replace("[0]", "")
        super(WriteDriverIn, self).save_result(cell_name, pin, *args, **kwargs)

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.write_driver_array = self.options.write_driver_array or OPTS.write_driver_array

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--write_driver_array", default=None)

    def get_cell_name(self):
        if not hasattr(self, "sample_array"):
            self.sample_array = self.create_class_from_opts("write_driver_array",
                                                            columns=32,
                                                            word_size=32)
        return self.sample_array.child_mod.name

    def get_pins(self):
        pins = self.sample_array.child_mod.get_input_pins()
        if self.options.plot:
            return pins

        return [x if x.startswith("en") else x + "[0]" for x in pins]

    def make_dut(self, num_elements):
        load = self.create_class_from_opts("write_driver_array",
                                           columns=num_elements, word_size=num_elements)
        return load

    def get_dut_instance_statement(self, pin):
        conns = [x for x in self.load.pins]
        conns[conns.index(pin)] = "d"

        input_pins = self.load.original_dut.get_input_pins()
        for input_pin in input_pins:
            if not input_pin == pin:
                conns[conns.index(input_pin)] = "d_dummy"

        return f"X4 {' '.join(conns)} {self.load.name}"


WriteDriverIn.run_tests(__name__)
