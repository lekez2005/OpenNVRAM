import debug
from base import design, utils
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.sotfet.sf_bitline_logic import SfBitlineLogic


@library_import
class sot_bitline_logic_tap(design.design):
    """
    Nwell and Psub body taps for bitline logic
    """
    pin_names = []
    lib_name = "sot_bitline_logic_tap"


class SfBitlineLogicArray(design.design):
    """
    Array of data mask
    """
    mod_insts = []
    body_tap_insts = []
    bitcell_offsets = []
    tap_offsets = []
    bitline_mod = body_tap = None

    def __init__(self, word_size):
        assert word_size % 2 == 0, "Word Size must be even"
        design.design.__init__(self, "sf_bitline_logic_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.create_layout()

    def create_modules(self):
        self.bitline_mod = SfBitlineLogic(OPTS.bitline_logic)
        self.add_mod(self.bitline_mod)

        self.body_tap = sot_bitline_logic_tap(OPTS.bitline_logic_tap)
        self.add_mod(self.body_tap)

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_array()
        self.add_layout_pins()
        self.add_poly_dummy()

    def create_array(self):
        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns):
            name = "bitline_logic_{}".format(i)
            offset = vector(self.bitcell_offsets[i], 0)
            instance = self.add_inst(name=name, mod=self.bitline_mod, offset=offset)

            connection_str = "data[{0}] data_bar[{0}] mask[{0}] en bl[{0}] br[{0}] vdd gnd".format(i)
            self.connect_inst(connection_str.split())
            # copy layout pins
            for pin_name in ["data", "data_bar", "mask", "bl", "br"]:
                self.copy_layout_pin(instance, pin_name, pin_name+"[{0}]".format(i))

            self.mod_insts.append(instance)

        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

        self.width = max(self.mod_insts[-1].rx(), self.body_tap_insts[-1].rx())
        self.height = self.mod_insts[-1].uy()

    def add_layout_pins(self):
        pin_names = ["en", "vdd", "gnd"]
        for pin_name in pin_names:
            pins = self.mod_insts[0].get_pins(pin_name)
            for pin in pins:
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    width=self.width, height=pin.height())

    def add_poly_dummy(self):
        dummy_polys = self.get_gds_layer_shapes(self.bitline_mod, "po_dummy", "po_dummy")
        top_poly = max(dummy_polys, key=lambda x: x[1][1])
        bottom_poly = min(dummy_polys, key=lambda x: x[0][1])

        x_offset = self.width + self.poly_pitch - 0.5 * self.poly_width
        self.add_rect("po_dummy", offset=vector(x_offset, bottom_poly[0][1]), width=self.poly_width,
                      height=top_poly[1][1]-bottom_poly[0][1])

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("data[{0}]".format(i))
            self.add_pin("data_bar[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("mask[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        self.add_pin_list(["en", "vdd", "gnd"])
