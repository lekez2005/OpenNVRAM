import debug
from base import design
from base.utils import load_class
from base.vector import vector
from globals import OPTS


class sf_ml_precharge_array(design.design):
    """
    Array of matchline precharge
    """

    def __init__(self, rows, size=1):
        design.design.__init__(self, "ml_precharge_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.precharge = load_class('ml_precharge')(size=size)
        self.add_mod(self.precharge)

        self.rows = rows
        self.size = size

        self.width = self.precharge.width
        self.height = self.height = self.rows * self.precharge.height

        self.precharge_insts = []

        self.separate_vdd = OPTS.separate_vdd if hasattr(OPTS, 'separate_vdd') else False

        self.add_pins()
        self.create_layout()
        self.add_layout_pins()
        self.DRC_LVS()

    def add_pins(self):
        self.add_pin("precharge_bar")
        for i in range(self.rows):
            self.add_pin("ml[{0}]".format(i))
        self.add_pin("vdd")
        self.add_pin("gnd")
        if self.separate_vdd:
            self.add_pin("decoder_vdd")

    def create_layout(self):

        for row in range(self.rows):
            y_offset = row * self.precharge.height
            if row % 2 == 1:
                y_offset += self.precharge.height
                mirror = "MX"
            else:
                mirror = "R0"
            name = "precharge_{}".format(row)
            offset = vector(0, y_offset)
            self.precharge_insts.append(self.add_inst(name=name, mod=self.precharge, offset=offset, mirror=mirror))
            nwell_pin = ["decoder_vdd"] if self.separate_vdd else []
            self.connect_inst(["precharge_bar",
                               "ml[{0}]".format(row),
                               "vdd", "gnd"] + nwell_pin)

    def add_layout_pins(self):
        for row in range(self.rows):
            self.copy_layout_pin(self.precharge_insts[row], "ml", "ml[{0}]".format(row))
            self.copy_layout_pin(self.precharge_insts[row], "vdd", "vdd")
            self.copy_layout_pin(self.precharge_insts[row], "gnd", "gnd")
        precharge_pin = self.precharge_insts[0].get_pin("chb")
        self.add_layout_pin("precharge_bar", precharge_pin.layer, offset=vector(precharge_pin.lx(), 0),
                            width=precharge_pin.width(), height=self.height)


