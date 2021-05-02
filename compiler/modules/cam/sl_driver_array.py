from globals import OPTS
from modules import write_driver_array


class sl_driver_array(write_driver_array.write_driver_array):
    """
    Array of search line drivers
    """

    def get_name(self):
        return "sl_driver_array"

    @property
    def mod_name(self):
        return OPTS.cam_sl_driver

    @property
    def tap_name(self):
        return None

    @property
    def bus_pins(self):
        return ["sl", "slb", "din", "mask"]

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("din[{0}]".format(i))
            self.add_pin("sl[{0}]".format(i))
            self.add_pin("slb[{0}]".format(i))
            self.add_pin("mask[{0}]".format(i))

        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")
