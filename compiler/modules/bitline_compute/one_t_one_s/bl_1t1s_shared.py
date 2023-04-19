from base.design import design
from base.library_import import library_import
from globals import OPTS


@library_import
class bl_1t1s_shared(design):
    pin_names = ["BL", "BLB", "BR", "RWL", "WWL"]
    lib_name = OPTS.bitcell_mod
