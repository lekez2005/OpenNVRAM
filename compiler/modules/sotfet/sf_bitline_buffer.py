import debug
from base import design
from base.vector import vector
from globals import OPTS
from pgates.pinv import pinv


class SfBitlineBuffer(design.design):
    """
    Bitline driver buffers, should be a cascade of two inverters
    """
    in_inv = out_inv = None

    def __init__(self):

        design.design.__init__(self, "SfBitlineBuffer")
        debug.info(1, "Creating {0}".format(self.name))

        self.buffer_sizes = OPTS.bitline_buffer_sizes  # type: list[int]

        self.add_pins()
        self.create_modules()
        self.create_layout()

        self.width = 1
        self.height = 2

    def create_modules(self):
        self.in_inv = pinv(size=self.buffer_sizes[0], contact_nwell=False, contact_pwell=False)
        self.add_mod(self.in_inv)
        self.out_inv = pinv(size=self.buffer_sizes[1], contact_nwell=False, contact_pwell=False)
        self.add_mod(self.out_inv)

    def create_layout(self):
        pin_combinations = [("bl_in", "bl_mid", "bl_out"), ("br_in", "br_mid", "br_out")]
        module_suffixes = ["bl", "br"]

        for i in [0, 1]:
            pin_combination = pin_combinations[i]
            self.add_inst("Xin_inv_" + module_suffixes[i], self.in_inv, offset=vector(0, 0))
            self.connect_inst([pin_combination[0], pin_combination[1], "vdd", "gnd"])

            self.add_inst("Xout_inv_" + module_suffixes[i], self.out_inv, offset=vector(0, 0))
            self.connect_inst([pin_combination[1], pin_combination[2], "vdd", "gnd"])

    def add_pins(self):
        self.add_pin_list(["bl_in", "br_in", "bl_out", "br_out", "vdd", "gnd"])
