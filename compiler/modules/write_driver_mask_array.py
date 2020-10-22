from importlib import reload

import debug
from base import design, utils
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.write_driver_mask import write_driver_mask


@library_import
class write_driver_mask_tap(design.design):
    """
    Nwell and Psub body taps for write_driver_mask_
    Assumes there is a pwell body tap below the write driver
    """
    pin_names = []
    lib_name = OPTS.write_driver_tap


class write_driver_mask_array(design.design):
    """
    Array of Masked write drivers
    """

    mod_insts = []
    body_tap_insts = []

    def __init__(self, columns, word_size):
        design.design.__init__(self, "write_driver_mask_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.write_driver))
        self.mod_write_driver = getattr(c, OPTS.write_driver)
        self.driver = self.mod_write_driver()
        self.add_mod(self.driver)

        self.columns = columns
        self.word_size = word_size
        self.words_per_row = int(columns / word_size)

        self.height = self.driver.height

        self.create_layout()
        self.DRC_LVS()

    def create_modules(self):
        self.driver = write_driver_mask()
        self.add_mod(self.driver)

        self.body_tap = write_driver_mask_tap()
        self.add_mod(self.body_tap)

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_array()
        self.add_layout_pins()
        self.fill_array_layer("nwell", self.driver)
        self.add_dummy_poly(self.driver, self.mod_insts, self.words_per_row,
                            from_gds=True)

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("data[{0}]".format(i))
            self.add_pin("data_bar[{0}]".format(i))
        for i in range(0, self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        for i in range(self.word_size):
            self.add_pin("mask_bar[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("en_bar")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_array(self):
        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns, self.words_per_row):
            bit_index = int(i / self.words_per_row)
            name = "driver_{}".format(bit_index)
            offset = vector(self.bitcell_offsets[i], 0)
            instance = self.add_inst(name=name, mod=self.driver, offset=offset)

            connections = ["data[{0}]".format(bit_index), "data_bar[{0}]".format(bit_index),
                           "mask_bar[{0}]".format(bit_index), "en", "en_bar",
                           "bl[{0}]".format(bit_index), "br[{0}]".format(bit_index), "vdd", "gnd"]

            self.connect_inst(connections)
            # copy layout pins
            for pin_name in ["bl", "br", "mask_bar", "data", "data_bar"]:
                self.copy_layout_pin(instance, pin_name, "{}[{}]".format(pin_name, bit_index))

            self.mod_insts.append(instance)

        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

        self.width = max(self.mod_insts[-1].rx(), self.body_tap_insts[-1].rx())
        self.height = self.mod_insts[-1].uy()

    def add_layout_pins(self):
        pin_names = ["en", "en_bar", "vdd", "gnd"]
        for pin_name in pin_names:
            pins = self.mod_insts[0].get_pins(pin_name)
            for pin in pins:
                self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(),
                                    width=self.width - pin.lx(), height=pin.height())
