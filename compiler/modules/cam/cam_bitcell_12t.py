import design
import debug
from modules import bitcell
import utils
from tech import GDS, layer


class cam_bitcell_12t(bitcell.bitcell):
    """
    A single CAM bit cell (6T, 8T, etc.)  This module implements the
    single memory cell used in the design. It is a hand-made cell, so
    the layout and netlist should be available in the technology
    library.
    """

    pin_names = ["BL", "BR", "SL", "SLB", "WL", "WWL", "ML", "vdd", "gnd"]
    (width, height) = utils.get_libcell_size("cam_cell_12t", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "cam_cell_12t", GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, "cam_cell_12t")
        debug.info(2, "Create cam bitcell")

        self.width = cam_bitcell_12t.width
        self.height = cam_bitcell_12t.height
        self.pin_map = cam_bitcell_12t.pin_map
