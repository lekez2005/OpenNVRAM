from base.design import design, METAL2
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.push_rules.dual_bitcell_aligned_array import dual_bitcell_aligned_array


@library_import
class amp(design):
    """
    Contains sense amp imported from technology library
    """
    pin_names = "bl<0> bl<1> br<0> br<1> dout<1> dout<0>" \
                " dout_bar<1> dout_bar<0> en gnd preb sampleb vdd".split()
    lib_name = OPTS.sense_amp_mod


class SenseAmpArray(dual_bitcell_aligned_array):
    """
    Dynamically generated sense amp array of all bitlines
    """

    mod_rotation = GDS_ROT_90

    name = "sense_amp_array"
    mod_name = OPTS.sense_amp_class
    horizontal_pins = ["en", "preb", "sampleb", "vdd", "gnd"]
    bus_pins = ["bl", "br", "dout", "dout_bar"]

    def add_pins(self):
        for i in range(0, self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
            self.add_pin("dout[{0}]".format(i))
            self.add_pin("dout_bar[{0}]".format(i))

        self.add_pin_list(["en", "preb", "sampleb", "vdd", "gnd"])
