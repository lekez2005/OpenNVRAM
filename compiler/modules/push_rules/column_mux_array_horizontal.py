from base.design import design, METAL2
from base.hierarchy_layout import GDS_ROT_270, GDS_ROT_90
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.single_level_column_mux_array import single_level_column_mux_array


@library_import
class column_mux(design):
    """Column mux"""
    pin_names = "bl bl_out br br_out gnd sel vdd".split()
    lib_name = OPTS.column_mux_mod


class ColumnMuxArrayHorizontal(single_level_column_mux_array):
    rotation_for_drc = GDS_ROT_270

    def add_pins(self):
        super().add_pins()
        self.add_pin("vdd")

    def add_modules(self):
        self.mux = self.create_mod_from_str(OPTS.column_mux_class, rotation=GDS_ROT_90)
        self.child_mod = self.mux

    def setup_layout_constants(self):
        self.route_height = (self.words_per_row + 2) * self.bus_pitch + self.get_line_end_space(METAL2)
        self.bitcell_offsets = [(1 + x) * self.mux.width for x in range(self.columns)]

    def create_array(self):
        self.child_insts = []
        bitcell_width = self.mux.width
        for col_num in range(self.columns):
            name = "MUX{0}".format(col_num)
            if col_num % 2 == 0:
                x_offset = (1 + col_num) * bitcell_width
                mirror = "R0"
            else:
                x_offset = (2 + col_num) * bitcell_width
                mirror = "MY"
            self.child_insts.append(self.add_inst(name, mod=self.mux,
                                                  offset=vector(x_offset, self.route_height),
                                                  mirror=mirror))
            self.connect_inst("bl[{0}] bl_out[{1}] br[{0}] br_out[{1}] gnd sel[{2}] vdd"
                              .format(col_num, int(col_num / self.words_per_row),
                                      col_num % self.words_per_row).split())

    def get_output_bitlines(self, col):
        bl_out, br_out = self.child_insts[col].get_pin("bl_out"), self.child_insts[col].get_pin("br_out")
        if col % 2 == 0:
            return bl_out, br_out
        else:
            return br_out, bl_out

    def add_layout_pins(self):
        for col_num in range(self.columns):
            child_insts = self.child_insts[col_num]
            if col_num % 2 == 0:
                bl_pin, br_pin = "bl", "br"
            else:
                bl_pin, br_pin = "br", "bl"
            self.copy_layout_pin(child_insts, bl_pin, "bl[{}]".format(col_num))
            self.copy_layout_pin(child_insts, br_pin, "br[{}]".format(col_num))

        for pin_name in ["vdd", "gnd"]:
            for pin in self.child_insts[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    height=pin.height(), width=self.child_insts[-1].rx())
