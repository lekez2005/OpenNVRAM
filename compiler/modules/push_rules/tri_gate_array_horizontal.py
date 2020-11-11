from base.design import design
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from globals import OPTS
from modules.push_rules.dual_bitcell_aligned_array import dual_bitcell_aligned_array


@library_import
class tri_gate(design):
    """
    Contains tri-state driver imported from technology library
    """
    pin_names = "en gnd in<0> in<1> out<0> out<1> vdd".split()
    lib_name = OPTS.tri_gate_mod


class TriGateArray(dual_bitcell_aligned_array):
    """
    Dynamically generated tri gate array of all bitlines.  words_per_row
    """

    mod_rotation = GDS_ROT_90

    name = "tri_gate_array"
    mod_name = OPTS.tri_gate_class
    horizontal_pins = ["en", "vdd", "gnd"]
    bus_pins = ["in", "out"]

    def add_pins(self):
        """create the name of pins depend on the word size"""
        for i in range(self.word_size):
            self.add_pin("in[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("out[{0}]".format(i))
        for pin in ["en", "vdd", "gnd"]:
            self.add_pin(pin)
