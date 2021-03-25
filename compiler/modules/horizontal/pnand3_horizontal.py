from base import unique_meta, utils
from base.vector import vector
from modules.horizontal.pgate_horizontal import pgate_horizontal
from pgates.ptx_spice import ptx_spice


class pnand3_horizontal(pgate_horizontal, metaclass=unique_meta.Unique):
    all_pmos = True
    all_nmos = False
    num_poly_contacts = 3

    @classmethod
    def get_name(cls, size=1, beta=None):
        beta, beta_suffix = cls.get_beta(beta, size)
        name = "pnand3_horizontal_{:.3g}{}".format(size, beta_suffix).replace(".", "__")
        return name

    def add_pins(self):
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def get_power_indices(self, is_nmos):
        if is_nmos:
            return [0]
        else:
            return [1, 3]

    def get_output_indices(self, is_nmos):
        if is_nmos:
            return [3]
        else:
            return [0, 2]

    def calculate_constraints(self):
        self.num_fingers = 3
        self.nmos_finger_width = utils.ceil(3 * self.min_tx_width * self.size)
        self.pmos_finger_width = utils.ceil(self.beta * self.min_tx_width * self.size)

    def get_ptx_connections(self):
        from pgates.pnand3 import get_ptx_connections
        return get_ptx_connections(self)
