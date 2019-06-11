import debug
from base import design, utils
from base.vector import vector
from modules.sotfet.sf_bitline_buffer import SfBitlineBuffer


class SfBitlineBufferArray(design.design):
    """
    Bitline driver buffers, should be a cascade of two inverters
    """
    mod_insts = bitcell_offsets = tap_offsets = []

    def __init__(self, word_size):

        design.design.__init__(self, "SfBitlineBufferArray")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.add_pins()

        self.bitline_buffer = SfBitlineBuffer()
        self.add_mod(self.bitline_buffer)

        self.create_layout()

        self.width = self.bitline_buffer.width * self.columns
        self.height = self.bitline_buffer.height

    def create_layout(self):

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns, self.words_per_row):
            name = "bitline_buffer{}".format(i)
            base = vector(self.bitcell_offsets[i], 0)

            self.mod_insts.append(self.add_inst(name=name, mod=self.bitline_buffer, offset=base))

            connection_str = "bl_in[{col}] br_in[{col}] bl_out[{col}] br_out[{col}] " \
                             "vdd gnd".format(col=i)

            self.connect_inst(connection_str.split(' '))

    def add_pins(self):

        for i in range(self.word_size):
            self.add_pin("bl_in[{0}]".format(i))
            self.add_pin("br_in[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl_out[{0}]".format(i))
            self.add_pin("br_out[{0}]".format(i))

        self.add_pin_list(["vdd", "gnd"])
