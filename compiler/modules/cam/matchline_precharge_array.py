import debug
from base import design
from base.vector import vector
from globals import OPTS


class MatchlinePrechargeArray(design.design):
    """
    Array of matchline precharge
    """

    def __init__(self, rows, size=1):
        design.design.__init__(self, "ml_precharge_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.precharge = self.create_mod_from_str(OPTS.ml_precharge, size=size)
        self.add_mod(self.precharge)

        self.rows = rows
        self.size = size

        self.width = self.precharge.width
        self.height = self.height = self.rows * self.precharge.height

        self.precharge_insts = []

        self.add_pins()
        self.create_layout()
        self.add_layout_pins()
        self.DRC_LVS()

    def add_pins(self):
        self.add_pin("precharge_en_bar")
        for i in range(self.rows):
            self.add_pin("ml[{0}]".format(i))
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        bitcell_array_cls = self.import_mod_class_from_str(OPTS.bitcell_array)
        y_offsets, _, _ = bitcell_array_cls.calculate_y_offsets(num_rows=self.rows)

        for row in range(self.rows):
            y_offset = y_offsets[row]
            if row % 2 == 0:
                y_offset += self.precharge.height
                mirror = "MX"
            else:
                mirror = "R0"
            name = "precharge_{}".format(row)
            offset = vector(0, y_offset)
            self.precharge_insts.append(self.add_inst(name=name, mod=self.precharge,
                                                      offset=offset, mirror=mirror))
            self.connect_inst(["precharge_en_bar",
                               "ml[{0}]".format(row), "vdd", "gnd"])

    def add_layout_pins(self):
        for row in range(self.rows):
            self.copy_layout_pin(self.precharge_insts[row], "ml", "ml[{0}]".format(row))
            self.copy_layout_pin(self.precharge_insts[row], "vdd", "vdd")
            self.copy_layout_pin(self.precharge_insts[row], "gnd", "gnd")
        precharge_pin = self.precharge_insts[0].get_pin("precharge_en_bar")
        self.add_layout_pin("precharge_en_bar", precharge_pin.layer,
                            offset=vector(precharge_pin.lx(), 0),
                            width=precharge_pin.width(), height=self.height)
