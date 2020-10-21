from base.design import design
from base.library_import import library_import


@library_import
class sense_amp_br_reset(design):
    pin_names = "bl br br_reset dout en en_bar gnd vdd vref".split()
    lib_name = "sense_amp_br_reset"
