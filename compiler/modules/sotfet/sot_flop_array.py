import debug
from base import utils
from base.design import design
from base.library_import import library_import
from base.vector import vector


@library_import
class sot_dual_flop_tap(design):
    """
    Nwell and Psub body tap for flops
    """
    pin_names = []
    lib_name = "dual_flop_tap"


@library_import
class dual_flop(design):
    """
    Contains two flops in one layout
    """
    pin_names = "clk din<0> din<1> dout<0> dout<1> dout_bar<0> dout_bar<1> vdd gnd".split()
    lib_name = "dual_flop"


class sot_flop_array(design):

    word_size = 0
    flop_mod = body_tap = None
    ms_inst = []
    body_tap_insts = []
    bitcell_offsets = tap_offsets = []

    def __init__(self, columns, word_size, align_bitcell=False, flop_mod=None,
                 flop_tap_name=None):
        assert word_size % 2 == 0, "Word Size must be even"
        name = "sot_flop_array_c{}".format(word_size)
        design.__init__(self, name=name)
        debug.info(1, "Creating {0}".format(self.name))

        assert columns == word_size

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_array()
        self.add_layout_pins()
        self.add_poly_dummy()

    def create_modules(self):
        self.flop_mod = dual_flop()
        self.add_mod(self.flop_mod)

        self.body_tap = sot_dual_flop_tap()
        self.add_mod(self.body_tap)

    def create_array(self):

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.word_size)

        for i in range(0, self.word_size, 2):
            name = "dff{0}_{1}".format(i, i+1)
            offset = vector(self.bitcell_offsets[i], 0)
            instance = self.add_inst(name=name, mod=self.flop_mod, offset=offset)
            self.ms_inst.append(instance)

            connection_str = "clk din[{c0}] din[{c1}] dout[{c0}] dout[{c1}] " \
                             " dout_bar[{c0}] dout_bar[{c1}] vdd gnd"
            self.connect_inst(connection_str.format(c0=i, c1=i+1).split())
            self.copy_layout_pin(instance, "din<0>", "din[{}]".format(i))
            self.copy_layout_pin(instance, "din<1>", "din[{}]".format(i+1))
            self.copy_layout_pin(instance, "dout<0>", "dout[{}]".format(i))
            self.copy_layout_pin(instance, "dout<1>", "dout[{}]".format(i+1))
            self.copy_layout_pin(instance, "dout_bar<0>", "dout_bar[{}]".format(i))
            self.copy_layout_pin(instance, "dout_bar<1>", "dout_bar[{}]".format(i+1))

        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

        self.width = max(self.ms_inst[-1].rx(), self.body_tap_insts[-1].rx())
        self.height = self.ms_inst[-1].uy()

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("din[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("dout[{0}]".format(i))
            self.add_pin("dout_bar[{0}]".format(i))
        self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def add_layout_pins(self):
        pin_names = ["vdd", "gnd", "clk"]
        for pin_name in pin_names:
            pins = self.ms_inst[0].get_pins(pin_name)
            for pin in pins:
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    width=self.width, height=pin.height())

    def add_poly_dummy(self):
        dummy_polys = self.get_gds_layer_shapes(self.flop_mod, "po_dummy", "po_dummy")
        # only two tallest dummies need additional dummies
        top_two = sorted(dummy_polys, key=lambda x: x[1][1]-x[0][1], reverse=True)[:2]
        for rect in top_two:
            x_offset = self.width - 0.5*self.poly_width + self.poly_pitch
            height = rect[1][1] - rect[0][1]
            self.add_rect("po_dummy", offset=vector(x_offset, rect[0][1]), width=self.poly_width,
                          height=height)
