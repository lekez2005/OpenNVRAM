import debug
import design
import utils
from tech import GDS, layer


class cam_sl_driver(design.design):
    """Search line driver. This is a handmade cell"""
    pin_names = ["en", "din", "sl", "slb", "mask", "vdd", "gnd"]
    (width, height) = utils.get_libcell_size("cam_sl_driver", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "cam_sl_driver", GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, "cam_sl_driver")
        debug.info(2, "Create cam_sl_driver")

        self.width = cam_sl_driver.width
        self.height = cam_sl_driver.height
        self.pin_map = cam_sl_driver.pin_map
