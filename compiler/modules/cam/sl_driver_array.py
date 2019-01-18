from importlib import reload

import debug
from base import design
from globals import OPTS
from modules import write_driver_array


class sl_driver_array(write_driver_array.write_driver_array):
    """
    Array of search line drivers
    """

    def __init__(self, columns, word_size):
        design.design.__init__(self, "sl_driver_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.cam_sl_driver))
        self.mod_sl_driver = getattr(c, OPTS.cam_sl_driver)
        self.driver = self.mod_sl_driver()
        self.add_mod(self.driver)

        self.driver_insts = []

        self.columns = columns
        self.word_size = word_size
        self.words_per_row = int(columns / word_size)

        self.height = self.driver.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.columns):
            self.add_pin("din[{0}]".format(i))
            self.add_pin("sl[{0}]".format(i))
            self.add_pin("slb[{0}]".format(i))
            self.add_pin("mask[{0}]".format(i))

        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def get_connections(self, i):
        index = int(i/self.words_per_row)
        return ["din[{0}]".format(index),
                           "sl[{0}]".format(index),
                           "slb[{0}]".format(index),
                           "mask[{0}]".format(index),
                           "en", "vdd", "gnd"]



    def add_layout_pins(self):
        self.add_common_pins()
        for i in range(self.word_size):
            mask_pin = self.driver_insts[i].get_pin("mask")
            self.add_layout_pin(text="mask[{0}]".format(i),
                                layer=mask_pin.layer,
                                offset=mask_pin.ll(),
                                width=mask_pin.width(),
                                height=mask_pin.height())
            sl_pin = self.driver_insts[i].get_pin("sl")
            self.add_layout_pin(text="sl[{0}]".format(i),
                                layer=sl_pin.layer,
                                offset=sl_pin.ll(),
                                width=sl_pin.width(),
                                height=sl_pin.height())

            slb_pin = self.driver_insts[i].get_pin("slb")
            self.add_layout_pin(text="slb[{0}]".format(i),
                                layer=slb_pin.layer,
                                offset=slb_pin.ll(),
                                width=slb_pin.width(),
                                height=slb_pin.height())









