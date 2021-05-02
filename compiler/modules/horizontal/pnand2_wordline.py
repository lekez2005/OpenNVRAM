from base import unique_meta, utils, contact
from base.design import METAL1
from base.vector import vector
from modules.horizontal.wordline_pgate_horizontal import wordline_pgate_horizontal


class pnand2_wordline(wordline_pgate_horizontal, metaclass=unique_meta.Unique):
    nmos_pmos_nets_aligned = False
    pgate_name = "pnand2_wordline"
    num_fingers = 2
    num_poly_contacts = 2

    def get_ptx_connections(self):
        return [
            (self.pmos, ["vdd", "A", "Z", "vdd"]),
            (self.pmos, ["Z", "B", "vdd", "vdd"]),
            (self.nmos, ["Z", "B", "net1", "gnd"]),
            (self.nmos, ["net1", "A", "gnd", "gnd"])
        ]

    def get_source_drain_connections(self):
        return [
            ([0], [0, 2]),
            ([2], [1])
        ]

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "Z", "vdd", "gnd"])

    def calculate_constraints(self):
        if self.bitcell_top_overlap and self.max_num_fingers <= self.num_fingers:
            raise ValueError("Bitcell height is too low to support {}")

        self.nmos_finger_width = utils.round_to_grid(self.num_fingers * self.size *
                                                     self.min_tx_width)
        self.pmos_finger_width = utils.round_to_grid(self.beta * self.size * self.min_tx_width)

    def connect_inputs(self):
        pin_names = ["A", "B", "C"]
        poly_y, _, _ = self.get_poly_y_offsets(self.num_fingers)

        contact_mid_x = self.gate_contact_x + 0.5 * self.contact_width
        for i, pin_name in zip(range(self.num_fingers), pin_names):
            contact_mid_y = poly_y[i] + 0.5 * self.poly_width
            self.add_poly_contact(contact_mid_x, contact_mid_y)
            self.add_layout_pin_center_rect(pin_name, METAL1,
                                            offset=vector(contact_mid_x, contact_mid_y),
                                            width=contact.poly.second_layer_height,
                                            height=contact.poly.second_layer_width)


class pnand3_wordline(pnand2_wordline):
    pgate_name = "pnand3_wordline"
    num_fingers = 3
    num_poly_contacts = 3

    def get_source_drain_connections(self):
        return [
            ([0], [0, 2]),
            ([3], [1, 3])
        ]

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def get_ptx_connections(self):
        from pgates.pnand3 import get_ptx_connections
        return get_ptx_connections(self)


class pnor2_wordline(pnand2_wordline):
    pgate_name = "pnor2_wordline"
    num_fingers = 2
    num_poly_contacts = 2

    def get_source_drain_connections(self):
        return [
            ([0, 2], [0]),
            ([1], [2])
        ]

    def calculate_constraints(self):
        if self.bitcell_top_overlap and self.max_num_fingers <= self.num_fingers:
            raise ValueError("Bitcell height is too low to support {}")

        self.nmos_finger_width = utils.round_to_grid(self.size * self.min_tx_width)
        self.pmos_finger_width = utils.round_to_grid(self.num_fingers * self.beta *
                                                     self.size * self.min_tx_width)

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "Z", "vdd", "gnd"])

    def get_ptx_connections(self):
        from pgates.pnor2 import get_ptx_connections
        return get_ptx_connections(self)


class pnor3_wordline(pnor2_wordline):
    pgate_name = "pnor3_wordline"
    num_fingers = 3
    num_poly_contacts = 3

    def get_source_drain_connections(self):
        return [
            ([0, 2], [0]),
            ([1, 3], [3])
        ]

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def get_ptx_connections(self):
        from pgates.pnor3 import get_ptx_connections
        return get_ptx_connections(self)
