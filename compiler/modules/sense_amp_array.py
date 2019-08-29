from importlib import reload

import debug
from base import design
from base import utils
from base.vector import vector
from globals import OPTS


class sense_amp_array(design.design):
    """
    Array of sense amplifiers to read the bitlines through the column mux.
    Dynamically generated sense amp array for all bitlines.
    """

    amp = None
    body_tap = None
    bitcell_offsets = []
    tap_offsets = []
    amp_insts = []
    body_tap_insts = []

    def __init__(self, word_size, words_per_row):
        design.design.__init__(self, "sense_amp_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = words_per_row
        self.row_size = self.word_size * self.words_per_row

        self.create_modules()

        self.height = self.amp.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def create_modules(self):
        c = reload(__import__(OPTS.sense_amp))
        mod_sense_amp = getattr(c, OPTS.sense_amp)
        self.amp = mod_sense_amp()
        self.add_mod(self.amp)

        if hasattr(OPTS, 'sense_amp_tap'):
            c = reload(__import__(OPTS.sense_amp_tap))
            mod_sense_amp_tap = getattr(c, OPTS.sense_amp_tap)
            self.body_tap = mod_sense_amp_tap()
            self.add_mod(self.amp)
        else:
            self.body_tap = None

    def add_pins(self):

        for i in range(0, self.row_size, self.words_per_row):
            index = int(i/self.words_per_row)
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
            self.add_pin("data[{0}]".format(index))

        self.add_pin("en")
        self.add_pin("en_bar")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        self.add_sense_amp()
        self.add_layout_pins()
        self.add_poly_dummy()

    def add_sense_amp(self):

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.row_size)

        self.amp_insts = []
        
        for i in range(0, self.row_size, self.words_per_row):
            name = "sa_d{0}".format(i)
            amp_position = vector(self.bitcell_offsets[i], 0)
            self.amp_insts.append(self.add_inst(name=name, mod=self.amp, offset=amp_position))
            self.connect_inst(self.get_connections(i))

        if self.body_tap is not None:
            for x_offset in self.tap_offsets:
                self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                         offset=vector(x_offset, 0)))
                self.connect_inst([])

        self.width = self.amp_insts[-1].rx()

    def get_connections(self, index):
        return ["bl[{0}]".format(index), "br[{0}]".format(index), "data[{0}]".format(index),
                "en", "en_bar", "vdd", "gnd"]

    def extend_vertical_pins(self, pin_name, output_name=None):
        if output_name is None:
            output_name = pin_name
        for i in range(len(self.amp_insts)):
            index = int(i / self.words_per_row)
            self.copy_layout_pin(self.amp_insts[i], pin_name, output_name + "[{}]".format(index))

    def extend_horizontal_pins(self, pin_name):
        pins = self.amp_insts[0].get_pins(pin_name)
        for pin in pins:
            self.add_layout_pin(pin_name, pin.layer, pin.ll(), self.width - pin.lx(), pin.height())

    def add_layout_pins(self):

        self.extend_vertical_pins("bl")
        self.extend_vertical_pins("br")
        self.extend_vertical_pins("dout", "data")

        self.extend_horizontal_pins("vdd")
        self.extend_horizontal_pins("gnd")
        self.extend_horizontal_pins("en")
        self.extend_horizontal_pins("en_bar")

    def add_poly_dummy(self):
        dummy_polys = self.get_gds_layer_shapes(self.amp, "po_dummy", "po_dummy")
        top_poly = max(dummy_polys, key=lambda x: x[1][1])
        bottom_poly = min(dummy_polys, key=lambda x: x[0][1])

        x_offset = self.width + self.poly_pitch - 0.5 * self.poly_width
        self.add_rect("po_dummy", offset=vector(x_offset, bottom_poly[0][1]), width=self.poly_width,
                      height=top_poly[1][1]-bottom_poly[0][1])

    def analytical_delay(self, slew, load=0.0):
        return self.amp.analytical_delay(slew=slew, load=load)
