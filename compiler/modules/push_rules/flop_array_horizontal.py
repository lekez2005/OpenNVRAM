from base.design import design
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from globals import OPTS
from modules.push_rules.dual_bitcell_aligned_array import dual_bitcell_aligned_array


@library_import
class flop(design):
    """
    Contains two bitline logic cells stacked vertically
    """
    pin_names = "clk din<1> din<0> dout<1> dout<0> dout_bar<1> dout_bar<0> gnd vdd".split()
    lib_name = OPTS.flop_mod


class FlopArray(dual_bitcell_aligned_array):
    """
    Dynamically generated tri gate array of all bitlines.  words_per_row
    """

    mod_rotation = GDS_ROT_90

    name = "flop_array"
    mod_name = OPTS.flop_class
    horizontal_pins = ["clk", "vdd", "gnd"]
    bus_pins = ["din", "dout", "dout_bar"]

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("din[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("dout[{0}]".format(i))
            self.add_pin("dout_bar[{0}]".format(i))
        self.add_pin_list(["clk", "vdd", "gnd"])
