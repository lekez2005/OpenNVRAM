from base.design import design
from base.vector import vector
from modules.bitline_compute.and_test import and_test
from pgates.ptx_spice import ptx_spice


class and_inv(design):
    def __init__(self):
        super().__init__("and_inv")

        self.add_pins()
        self.make_connections()

    def add_pins(self):
        self.add_pin("A")
        self.add_pin("B")
        self.add_pin("out")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def make_connections(self):
        and_g = and_test()
        self.add_mod(and_g)

        nmos = ptx_spice(width=0.1) # in microns
        self.add_mod(nmos)

        pmos = ptx_spice(width=0.2, tx_type="pmos")
        self.add_mod(pmos)

        # add instances, always connect immediately
        self.add_inst("my_and", and_g, offset=vector(0, 0))
        self.connect_inst(["A", "B", "and_output", "vdd", "gnd"])

        self.add_inst("my_nmos", mod=nmos, offset=vector(0, 0))

        self.connect_inst(["out", "and_output", "gnd", "gnd"])

        self.add_inst("my_pmos", mod=pmos, offset=vector(0, 0))
        self.connect_inst(["out", "and_output", "vdd", "vdd"])

