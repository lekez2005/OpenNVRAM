from base.design import design
from base.library_import import library_import
from globals import OPTS


@library_import
class bl_1t1s_separate(design):
    pin_names = ["BL", "BLB", "BR", "BRB", "RWL", "WWL"]
    lib_name = OPTS.bitcell_mod


@library_import
class bl_1t1s_tap(design):
    pin_names = ["vdd", "gnd"]
    lib_name = OPTS.body_tap_mod
