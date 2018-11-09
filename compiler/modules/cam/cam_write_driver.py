import debug
import design
import utils
from tech import GDS,layer

class cam_write_driver(design.design):
    """
    write driver to be active during write operations only.
    This module implements the write driver cell used in the design. It
    is a hand-made cell, so the layout and netlist should be available in
    the technology library.
    """

    pin_names = ["din", "bl", "br", "en", "mask", "gnd", "vdd"]
    (width,height) = utils.get_libcell_size("cam_write_driver", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "cam_write_driver", GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, "cam_write_driver")
        debug.info(2, "Create cam_write_driver")

        self.width = cam_write_driver.width
        self.height = cam_write_driver.height
        self.pin_map = cam_write_driver.pin_map

