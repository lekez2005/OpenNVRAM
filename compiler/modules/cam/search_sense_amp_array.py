from base import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS


@library_import
class SearchSenseAmp(design.design):
    """
    This module implements the single sense amp cell used in the design. It
    is a hand-made cell, so the layout and netlist should be available in
    the technology library.
    Sense amplifier to read a pair of bit-lines.
    """

    pin_names = ["vin", "vcomp", "dout", "en", "vdd", "gnd"]
    lib_name = OPTS.search_sense_amp_mod


class SearchSenseAmpArray(design.design):
    def __init__(self, rows):
        design.design.__init__(self, "search_sense_amp_array")

        self.rows = rows
        self.module_insts = []
        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.rows):
            self.add_pin("ml[{0}]".format(i))
        for i in range(self.rows):
            self.add_pin("dout[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vcomp")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        self.add_amp_array()
        self.width = self.module_insts[0].rx()
        self.height = self.module_insts[-1].uy()
        self.add_layout_pins()

    def add_amp_array(self):
        self.amp = self.create_mod_from_str(OPTS.search_sense_amp)
        self.add_mod(self.amp)
        for row in range(self.rows):
            y_offset = row*self.amp.height
            mirror = "R0"
            if row % 2 == 0:
                y_offset += self.amp.height
                mirror = "MX"
            self.module_insts.append(self.add_inst("amp[{}]".format(row), mod=self.amp, offset=vector(0, y_offset),
                                                   mirror=mirror))
            self.connect_inst(["ml[{}]".format(row), "vcomp", "dout[{}]".format(row),
                               "en", "vdd", "gnd"])

    def add_layout_pins(self):
        for pin_name in ["en", "vcomp"]:
            pin = self.module_insts[0].get_pin(pin_name)
            self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(), height=self.height, width=pin.width())

        for i in range(self.rows):
            inst = self.module_insts[i]
            self.copy_layout_pin(inst, "vin", "ml[{}]".format(i))
            self.copy_layout_pin(inst, "dout", "dout[{}]".format(i))

        for inst in set(self.module_insts[::2] + [self.module_insts[-1]]):
            self.copy_layout_pin(inst, "vdd", "vdd")
            self.copy_layout_pin(inst, "gnd", "gnd")

