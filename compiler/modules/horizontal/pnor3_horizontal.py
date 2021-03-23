from base import unique_meta, utils
from base.vector import vector
from modules.horizontal.pgate_horizontal import pgate_horizontal
from pgates.ptx_spice import ptx_spice


class pnor3_horizontal(pgate_horizontal, metaclass=unique_meta.Unique):
    all_pmos = False
    all_nmos = True
    num_poly_contacts = 3

    @classmethod
    def get_name(cls, size=1, beta=None):
        beta, beta_suffix = cls.get_beta(beta, size)
        name = "pnor3_horizontal_{:.3g}{}".format(size, beta_suffix).replace(".", "__")
        return name

    def add_pins(self):
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def get_power_indices(self, is_nmos):
        if is_nmos:
            return [0, 2]
        else:
            return [3]

    def get_output_indices(self, is_nmos):
        if is_nmos:
            return [1, 3]
        else:
            return [0]

    def calculate_constraints(self):
        self.num_fingers = 3
        self.nmos_finger_width = utils.ceil(1.25 * self.min_tx_width * self.size)
        self.pmos_finger_width = utils.ceil(3 * self.beta * self.min_tx_width * self.size)

    def add_ptx_insts(self):
        offset = vector(0, 0)
        self.pmos = ptx_spice(self.pmos_finger_width, mults=1, tx_type="pmos")

        self.pmos3_inst = self.add_inst(name="pnor3_pmos3", mod=self.pmos, offset=offset)
        self.connect_inst(["net2", "C", "Z", "vdd"])

        self.pmos2_inst = self.add_inst(name="pnor3_pmos2", mod=self.pmos, offset=offset)
        self.connect_inst(["net1", "B", "net2", "vdd"])

        self.pmos1_inst = self.add_inst(name="pnor3_pmos1", mod=self.pmos, offset=offset)
        self.connect_inst(["vdd", "A", "net1", "vdd"])

        self.nmos = ptx_spice(self.nmos_finger_width, mults=1, tx_type="nmos")

        self.nmos3_inst = self.add_inst(name="pnor3_nmos3", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "C", "gnd", "gnd"])

        self.nmos2_inst = self.add_inst(name="pnor3_nmos2", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "B", "gnd", "gnd"])

        self.nmos1_inst = self.add_inst(name="pnor3_nmos1", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "A", "gnd", "gnd"])
