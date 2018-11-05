import debug
import design
import utils
from tech import GDS, layer


class ms_flop_horz_pitch(design.design):
    """
    Flip flop whose height matches that of the bitcell
    """

    pin_names = ["din", "dout", "dout_bar", "clk", "vdd", "gnd"]
    (width,height) = utils.get_libcell_size("ms_flop_horz_pitch", GDS["unit"], layer["boundary"])
    pin_map = utils.get_libcell_pins(pin_names, "ms_flop_horz_pitch", GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, "ms_flop_horz_pitch")
        debug.info(2, "Create ms_flop_horz_pitch")

        self.width = ms_flop_horz_pitch.width
        self.height = ms_flop_horz_pitch.height
        self.pin_map = ms_flop_horz_pitch.pin_map

