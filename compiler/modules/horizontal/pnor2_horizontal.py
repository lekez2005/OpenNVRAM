from base import unique_meta, utils
from base.vector import vector
from modules.horizontal.pgate_horizontal import pgate_horizontal
from pgates.ptx_spice import ptx_spice


class pnor2_horizontal(pgate_horizontal, metaclass=unique_meta.Unique):
    all_pmos = False
    all_nmos = True
    num_poly_contacts = 2

    @classmethod
    def get_name(cls, size=1, beta=None):
        beta, beta_suffix = cls.get_beta(beta, size)
        name = "pnor2_horizontal_{:.3g}{}".format(size, beta_suffix).replace(".", "__")
        return name

    def add_pins(self):
        self.add_pin_list(["A", "B", "Z", "vdd", "gnd"])

    def get_power_indices(self, is_nmos):
        if is_nmos:
            return [0, 2]
        else:
            return [2]

    def get_output_indices(self, is_nmos):
        if is_nmos:
            return [1]
        else:
            return [0]

    def calculate_constraints(self):
        self.num_fingers = 2
        self.nmos_finger_width = utils.ceil(self.min_tx_width * self.size)
        self.pmos_finger_width = utils.ceil(2 * self.beta * self.min_tx_width * self.size)

    def get_ptx_connections(self):
        return [
            (self.pmos, ["vdd", "A", "net1", "vdd"]),
            (self.pmos, ["net1", "B", "Z", "vdd"]),
            (self.nmos, ["Z", "A", "gnd", "gnd"]),
            (self.nmos, ["Z", "B", "gnd", "gnd"]),
        ]
