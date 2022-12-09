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

    def create_modules(self):
        self.mux = self.create_mod_from_str(OPTS.column_mux, rotation=GDS_ROT_90)
        self.child_mod = self.mux

    def add_dummy_poly(self, *_, **__):
        pass
