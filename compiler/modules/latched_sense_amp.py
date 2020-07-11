from base import design
from base.library_import import library_import


@library_import
class latched_sense_amp(design.design):
    """
    Contains two bitline logic cells stacked vertically
    """
    pin_names = "bl br dout en preb sampleb vdd gnd".split()
    lib_name = "latched_sense_amp"
