from base.library_import import library_import
from modules import bitcell


@library_import
class sf_cam_bitcell(bitcell.bitcell):
    """
    A single SOTFET CAM bit cell. It is a hand-made cell, so
    the layout and netlist should be available in the technology
    library.
    """

    pin_names = ["BL", "BR", "ML", "WL", "gnd"]
    lib_name = "sot_cam_cell"
