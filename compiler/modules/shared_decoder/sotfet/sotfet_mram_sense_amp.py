from base.design import design
from base.library_import import library_import


@library_import
class sotfet_mram_sense_amp(design):
    pin_names = "bl br br_reset dout en gnd preb sampleb vdd vref".split()
    lib_name = "sotfet_mram_sense_amp"
