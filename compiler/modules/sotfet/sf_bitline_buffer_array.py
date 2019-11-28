import importlib

import debug
from base import design, utils
from base.vector import vector
from globals import OPTS


class SfBitlineBufferArray(design.design):
    """
    Bitline driver buffers, should be a cascade of two inverters
    """
    mod_insts = []
    body_tap_insts = []
    bitcell_offsets = tap_offsets = []

    def __init__(self, word_size):

        design.design.__init__(self, "SfBitlineBufferArray")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_array()

        self.width = max(self.mod_insts[-1].rx(), self.body_tap_insts[-1].rx())
        self.height = self.mod_insts[-1].uy()

        self.add_layout_pins()
        self.add_poly_dummy()

    def create_modules(self):
        module, class_name = OPTS.bitline_buffer.split(".")

        self.bitline_buffer = getattr(importlib.import_module(module), class_name)()
        self.add_mod(self.bitline_buffer)

        module, class_name = OPTS.bitline_buffer_tap.split(".")
        self.body_tap = getattr(importlib.import_module(module), class_name)(self.bitline_buffer)
        self.add_mod(self.body_tap)

    def create_array(self):

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns):
            name = "bitline_buffer{}".format(i)
            base = vector(self.bitcell_offsets[i], 0)

            instance = self.add_inst(name=name, mod=self.bitline_buffer, offset=base)
            self.mod_insts.append(instance)

            connection_str = "bl_in[{col}] br_in[{col}] bl_out[{col}] br_out[{col}] " \
                             "vdd gnd".format(col=i)

            self.connect_inst(connection_str.split(' '))
            # copy layout pins
            for pin_name in ["bl_in", "br_in", "bl_out", "bl_out"]:
                for j in range(2):
                    self.copy_layout_pin(instance, "{}".format(pin_name), "{}[{}]".format(pin_name, i))
        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

    def add_poly_dummy(self):
        x_offset = self.width + self.poly_pitch - 0.5 * self.poly_width
        # get rightmost poly
        poly_rects = self.bitline_buffer.get_layer_shapes("po_dummy", purpose="po_dummy")
        right_most = max(poly_rects, key=lambda x: x.rx())
        all_right_rects = list(filter(lambda x: x.rx() == right_most.rx(), poly_rects))
        top_rect = max(all_right_rects, key=lambda x: x.uy())
        bottom_rect = min(all_right_rects, key=lambda x: x.uy())
        self.add_rect("po_dummy", offset=vector(x_offset, bottom_rect.by()), width=self.poly_width,
                      height=top_rect.uy() - bottom_rect.by())

    def add_pins(self):

        for i in range(self.word_size):
            self.add_pin("bl_in[{0}]".format(i))
            self.add_pin("br_in[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl_out[{0}]".format(i))
            self.add_pin("br_out[{0}]".format(i))

        self.add_pin_list(["vdd", "gnd"])

    def add_layout_pins(self):
        pin_names = ["vdd", "gnd"]
        for col in range(self.columns):
            for pin_name in ["bl_out", "br_out"]:
                self.copy_layout_pin(self.mod_insts[col], pin_name, pin_name+"[{}]".format(col))
        for pin_name in pin_names:
            pins = self.mod_insts[0].get_pins(pin_name)
            for pin in pins:
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    width=self.width, height=pin.height())
