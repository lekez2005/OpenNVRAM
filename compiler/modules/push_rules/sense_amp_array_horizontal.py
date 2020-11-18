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

    def connect_mod(self, mod_index):
        word_index = mod_index * 2
        if mod_index % 2 == 0:
            template = "bl[{0}] bl[{1}] br[{0}] br[{1}] data[{1}] data[{0}]" \
                       " data_bar[{1}] data_bar[{0}] en gnd preb sampleb vdd"
        else:
            template = "br[{1}] br[{0}] bl[{1}] bl[{0}] data_bar[{0}] data_bar[{1}]" \
                       " data[{0}] data[{1}] en gnd preb sampleb vdd"

        self.connect_inst(template.format(word_index, word_index + 1).split())

    def add_pins(self):
        for i in range(0, self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
            self.add_pin("data[{0}]".format(i))

        self.add_pin_list(["en", "preb", "sampleb", "vdd", "gnd"])

    def copy_layout_pin(self, instance, pin_name, new_name=""):
        """Select dout or dout_bar pin depending on """
        if new_name.startswith("data_bar"):
            return
        elif new_name.startswith("data"):
            pin = instance.get_pin(pin_name)
            if "dout_bar" in pin_name:
                adjacent_name = pin_name.replace("dout_bar", "dout")
            else:
                adjacent_name = pin_name.replace("dout", "dout_bar")
            adjacent_pin = instance.get_pin(adjacent_name)
            bl_pin = instance.get_pin("bl<0>")
            mid_instance = 0.5 * (pin.cx() + adjacent_pin.cx())
            y_offset = pin.by() - self.get_line_end_space(METAL2) - self.m2_width

            self.add_rect(METAL2, offset=vector(pin.lx(), y_offset),
                          height=pin.by() - y_offset)

            self.add_rect(METAL2, offset=vector(pin.lx(), y_offset), width=mid_instance - pin.lx())
            self.add_layout_pin(new_name, METAL2,
                                offset=vector(mid_instance - 0.5 * self.m2_width, bl_pin.by()),
                                height=y_offset + self.m2_width - bl_pin.by())
            return
        super().copy_layout_pin(instance, pin_name, new_name)
