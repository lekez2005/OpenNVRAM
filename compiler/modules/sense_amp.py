import debug
from base import design
from base import utils
from tech import GDS, layer


class sense_amp(design.design):
    """
    This module implements the single sense amp cell used in the design. It
    is a hand-made cell, so the layout and netlist should be available in
    the technology library.
    Sense amplifier to read a pair of bit-lines.
    """

    pin_names = ["bl", "br", "dout", "en", "vdd", "gnd"]


    def __init__(self, name):
        design.design.__init__(self, name)
        debug.info(2, "Create sense_amp")

        (self.width, self.height) = utils.get_libcell_size(self.name, GDS["unit"], layer["boundary"])
        self.pin_map = utils.get_libcell_pins(sense_amp.pin_names, self.name, GDS["unit"], layer["boundary"])


    def analytical_delay(self, slew, load=0.0):
        from tech import spice
        r = spice["min_tx_r"]/(10)
        c_para = spice["min_tx_drain_c"]
        result = self.cal_delay_with_rc(r = r, c =  c_para+load, slew = slew)
        return self.return_delay(result.delay, result.slew)

    def analytical_power(self, proc, vdd, temp, load):
        """Returns dynamic and leakage power. Results in nW"""
        #Power in this module currently not defined. Returns 0 nW (leakage and dynamic).
        total_power = self.return_power()
        return total_power
