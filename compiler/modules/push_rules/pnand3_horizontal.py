from base import unique_meta, utils
from base.vector import vector
from modules.push_rules.pgate_horizontal import pgate_horizontal
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

    def add_ptx_insts(self):
        offset = vector(0, 0)
        self.pmos = ptx_spice(self.pmos_finger_width, mults=1, tx_type="pmos")
        self.pmos1_inst = self.add_inst(name="pnand3_pmos1", mod=self.pmos, offset=offset)
        self.connect_inst(["vdd", "A", "Z", "vdd"])

        self.pmos2_inst = self.add_inst(name="pnand3_pmos2", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "B", "vdd", "vdd"])

        self.pmos3_inst = self.add_inst(name="pnand3_pmos3", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "C", "vdd", "vdd"])

        self.nmos = ptx_spice(self.nmos_finger_width, mults=1, tx_type="nmos")
        self.nmos1_inst = self.add_inst(name="pnand3_nmos1", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "C", "net1", "gnd"])

        self.nmos2_inst = self.add_inst(name="pnand3_nmos2", mod=self.nmos, offset=offset)
        self.connect_inst(["net1", "B", "net2", "gnd"])

        self.nmos3_inst = self.add_inst(name="pnand3_nmos3", mod=self.nmos, offset=offset)
        self.connect_inst(["net2", "A", "gnd", "gnd"])
