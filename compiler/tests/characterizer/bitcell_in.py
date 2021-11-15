#!/usr/bin/env python3

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class BitcellIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True
    num_rows = num_cols = 1
    default_cols = [1]

    def save_result(self, cell_name, pin, *args, **kwargs):
        pin = pin.replace("[0]", "")
        super(BitcellIn, self).save_result(cell_name, pin, *args, **kwargs)

    def test_plot(self):
        if not self.options.plot:
            return
        pins = self.get_pins()
        for pin in pins:
            sweep_variable = "cols"
            # if pin.startswith("w"):
            #     sweep_variable = "cols"
            # else:
            #     sweep_variable = "rows"
            show_plot = pin == pins[-1]
            self.plot_results(self.get_cell_name(), [pin],
                              scale_by_x=self.options.scale_by_x, show_legend=True,
                              sweep_variable=sweep_variable, save_plot=self.options.save_plot,
                              show_plot=show_plot)

    def get_size_suffixes(self, num_elements):
        return [("cols", num_elements), ("wire", self.load.wire_length)]

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--bitcell_array", default=None)
        cls.parser.add_argument("-l", "--load", default=30e-15, type=float,
                                help="Capacitive load for resistance measurement")

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.bitcell_array = self.options.bitcell_array or OPTS.bitcell_array

    def get_cell_name(self) -> str:
        return self.create_class_from_opts("bitcell").name

    def get_pins(self):
        bitcell = self.create_class_from_opts("bitcell")
        pins = bitcell.get_input_pins() + bitcell.get_output_pins()
        if self.options.plot:
            return pins
        return [x + "[0]" for x in pins]

    def make_dut(self, num_elements):
        pin = self.dut_pin
        if pin.startswith("b"):
            self.num_rows = num_elements
            self.num_cols = 1
        else:
            self.num_rows = 1
            self.num_cols = num_elements

        name = "bitcell_array_r{}_c{}".format(self.num_rows, self.num_cols)
        load = self.create_class_from_opts("bitcell_array", cols=self.num_cols, rows=self.num_rows,
                                           name=name)
        return load

    def get_dut_instance_statement(self, pin) -> str:
        connections = []
        for conn in self.load.pins:
            if conn.startswith(pin):
                connections.append("d")
            elif pin.startswith("w") or pin.startswith("wwl") or pin.startswith("rwl"):
                if conn.startswith("b"):
                    # test wordline: set bitlines to vdd
                    connections.append("vdd")
                elif conn.startswith("w"):  # other word lines
                    connections.append("gnd")
                else:
                    connections.append(conn)
            elif pin.startswith("b"):
                if conn.startswith("w"):
                    # test bitline: set wordlines to gnd
                    connections.append("gnd")
                elif conn.startswith("b"):  # other bitlines
                    connections.append("d_dummy")
                else:
                    connections.append(conn)
            elif pin.startswith("ml"):
                if conn[:2] in ["wl", "bl", "br"]:
                    connections.append("gnd")
                else:
                    connections.append(conn)
            else:
                connections.append(conn)

        return f"X4 {' '.join(connections)} {self.load.name} \n"


BitcellIn.run_tests(__name__)
