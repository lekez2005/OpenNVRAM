from importlib import reload

import debug
from base import design
from globals import OPTS
from modules import write_driver_array


class cam_write_driver_array(write_driver_array.write_driver_array):
    """
    Array of CAM write drivers
    """

    def __init__(self, columns, word_size):
        design.design.__init__(self, "cam_write_driver_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.write_driver))
        self.mod_write_driver = getattr(c, OPTS.write_driver)
        self.driver = self.mod_write_driver()
        self.add_mod(self.driver)

        self.columns = columns
        self.word_size = word_size
        self.words_per_row = int(columns / word_size)

        self.height = self.driver.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("data[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        for i in range(self.word_size):
            self.add_pin("mask[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def get_connections(self, i):
        index = int(i / self.words_per_row)
        return ["data[{0}]".format(index),
                           "bl[{0}]".format(index),
                           "br[{0}]".format(index),
                           "mask[{0}]".format(index),
                           "en", "vdd", "gnd"]

    def add_layout_pins(self):
        super(cam_write_driver_array, self).add_layout_pins()
        for i in range(self.word_size):
            mask_pins = self.driver_insts[i].get_pins("mask")
            for mask_pin in mask_pins:
                self.add_layout_pin(text="mask[{0}]".format(i),
                                    layer=mask_pin.layer,
                                    offset=mask_pin.ll(),
                                    width=mask_pin.width(),
                                    height=mask_pin.height())


