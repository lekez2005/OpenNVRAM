import debug
from base import design, utils
from base.vector import vector

from modules.sotfet.sf_bitline_logic import SfBitlineLogic


class SfBitlineLogicArray(design.design):
    """
    Array of data mask
    """

    bitline_logic = None
    mod_insts = bitcell_offsets = tap_offsets = []

    def __init__(self, word_size):
        design.design.__init__(self, "sf_bitline_logic_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.add_pins()
        self.create_modules()
        self.create_layout()
        self.add_layout_pins()

        self.width = 10
        self.height = 10

    def create_modules(self):
        self.bitline_logic = SfBitlineLogic()
        self.add_mod(self.bitline_logic)

    def create_layout(self):
        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns, self.words_per_row):
            name = "bitline_logic{}".format(i)
            base = vector(self.bitcell_offsets[i], 0)

            self.mod_insts.append(self.add_inst(name=name, mod=self.bitline_logic, offset=base))

            connection_str = "clk data[{col}] data_bar[{col}] mask[{col}] mask_bar[{col}] " \
                             "write bl[{col}] br[{col}] vdd gnd".format(col=i)

            self.connect_inst(connection_str.split(' '))

    def add_layout_pins(self):
        pass

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("data[{0}]".format(i))
            self.add_pin("data_bar[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("mask[{0}]".format(i))
            self.add_pin("mask_bar[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        self.add_pin_list(["clk", "write", "vdd", "gnd"])
