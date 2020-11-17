from base.design import design
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.push_rules.bitcell_aligned_array import bitcell_aligned_array


@library_import
class driver(design):
    """
    Contains driver imported from technology library
    """
    pin_names = "bl br data data_bar en gnd mask vdd".split()
    lib_name = OPTS.write_driver_mod


class WriteDriverArray(bitcell_aligned_array):
    """
    Dynamically generated write driver array of all bitlines.  words_per_row
    """

    mod_rotation = GDS_ROT_90

    name = "write_driver_array"
    mod_name = OPTS.write_driver_class
    horizontal_pins = ["en", "vdd", "gnd"]
    bus_pins = ["bl", "br", "data", "data_bar", "mask"]

    def connect_mod(self, mod_index):
        if self.mirror and mod_index % 2 == 1:
            template = "br[{0}] bl[{0}] data_bar[{0}] data[{0}] en gnd mask vdd"
        else:
            template = "bl[{0}] br[{0}] data[{0}] data_bar[{0}] en gnd mask vdd"
        self.connect_inst(template.format(mod_index).split())

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("data[{0}]".format(i))
            self.add_pin("data_bar[{0}]".format(i))
        for i in range(0, self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        for i in range(self.word_size):
            self.add_pin("mask[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def add_layout_pins(self):
        for pin_name in self.child_mod.pins:
            if pin_name in self.horizontal_pins:
                for pin in self.child_insts[0].get_pins(pin_name):
                    self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                        height=pin.height(), width=self.width)
            elif pin_name in self.bus_pins:
                for word_index in range(len(self.child_insts)):
                    conn_index = self.insts.index(self.child_insts[word_index])
                    pin_index = self.child_mod.pins.index(pin_name)
                    actual_connection = self.conns[conn_index][pin_index]
                    self.copy_layout_pin(self.child_insts[word_index], pin_name,
                                         actual_connection)
            else:
                self.copy_layout_pin(self.child_insts[0], pin_name)
