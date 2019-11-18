from base.design import design
from base.library_import import library_import


@library_import
class sf_cam_bitcell(design):
    """
    A single SOTFET CAM bit cell. It is a hand-made cell, so
    the layout and netlist should be available in the technology
    library.
    """

    pin_names = ["BL", "BR", "ML", "WL", "mz1", "gnd"]
    lib_name = "sot_cam_cell"
