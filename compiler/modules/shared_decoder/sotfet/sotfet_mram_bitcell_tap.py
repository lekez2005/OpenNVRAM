from base.design import design
from base.library_import import library_import
from globals import OPTS


@library_import
class sotfet_mram_bitcell_tap(design):
    lib_name = OPTS.body_tap_mod
    pin_names = ["gnd"]
