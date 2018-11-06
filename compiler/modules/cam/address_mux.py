import debug
import design
import utils
from tech import GDS,layer


class address_mux(design.design):
    pin_names = ["in[0]", "in[1]", "sel", "sel_bar", "sel_all", "sel_all_bar", "out", "vdd", "gnd"]
    (width,height) = utils.get_libcell_size("address_mux", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "address_mux", GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, "address_mux")
        debug.info(2, "Create address_mux")

        self.width = address_mux.width
        self.height = address_mux.height
        self.pin_map = address_mux.pin_map
