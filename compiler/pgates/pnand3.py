from base.vector import vector
from .pnand2 import pnand2
from .ptx_spice import ptx_spice


class pnand3(pnand2):
    """
    This module generates gds of a parametrically sized 3-input nand.
    This model use ptx to generate a 3-input nand within a certain height.
    """
    nmos_scale = 2.5
    pmos_scale = 1
    num_tracks = 3

    mod_name = "nand3"

    def connect_to_gnd(self, _):
        super().connect_to_gnd(self.source_positions[0:1])

    def connect_s_or_d(self, _, __):
        super().connect_s_or_d(self.drain_positions, self.drain_positions[1:])

    @classmethod
    def get_class_name(cls):
        return "pnand3"

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def connect_inputs(self):
        y_shifts = [-self.gate_rail_pitch, 0, self.gate_rail_pitch]
        pin_names = ["A", "B", "C"]
        self.add_poly_contacts(pin_names, y_shifts)

    def add_ptx_inst(self):
        offset = vector(0, 0)
        self.pmos = ptx_spice(self.pmos_width, mults=self.tx_mults / 3, tx_type="pmos")
        self.pmos1_inst = self.add_inst(name="pnand3_pmos1", mod=self.pmos, offset=offset)
        self.connect_inst(["vdd", "A", "Z", "vdd"])

        self.pmos2_inst = self.add_inst(name="pnand3_pmos2", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "B", "vdd", "vdd"])

        self.pmos3_inst = self.add_inst(name="pnand3_pmos3", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "C", "vdd", "vdd"])

        self.nmos = ptx_spice(self.nmos_width, mults=self.tx_mults / 3, tx_type="nmos")
        self.nmos1_inst = self.add_inst(name="pnand3_nmos1", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "C", "net1", "gnd"])

        self.nmos2_inst = self.add_inst(name="pnand3_nmos2", mod=self.nmos, offset=offset)
        self.connect_inst(["net1", "B", "net2", "gnd"])

        self.nmos3_inst = self.add_inst(name="pnand3_nmos3", mod=self.nmos, offset=offset)
        self.connect_inst(["net2", "A", "gnd", "gnd"])
