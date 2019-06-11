from base.vector import vector
from globals import OPTS
from modules import bank
from modules.sotfet.sf_bitline_buffer_array import SfBitlineBufferArray
from modules.sotfet.sf_bitline_logic_array import SfBitlineLogicArray
from modules.sotfet.logic_buffers import LogicBuffers


class SfCamBank(bank.bank):
    bitcell = bitcell_array = wordline_driver = decoder = search_sense_amp_array = ml_precharge_array = None
    msf_data_in = msf_address = tag_flop_array = bitline_buffer_array = bitline_logic_array = logic_buffers = None

    bitcell_array_inst = ml_precharge_array_inst = search_sense_inst = tag_flop_array_inst = row_decoder_inst = None
    bitline_buffer_array_inst = bitline_logic_array_inst = data_in_flops_inst = mask_in_flops_inst = None
    wordline_driver_inst = logic_buffers_inst = None

    def create_modules(self):
        self.bitcell = self.create_module('bitcell')
        self.bitcell_array = self.create_module('bitcell_array', cols=self.num_cols, rows=self.num_rows)
        self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows,
                                                  buffer_stages=OPTS.wordline_buffers)
        # self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows)
        self.search_sense_amp_array = self.create_module('search_sense_amp_array', rows=self.num_rows)
        self.ml_precharge_array = self.create_module('ml_precharge_array', rows=self.num_rows, size=3)
        self.msf_data_in = self.create_module('ms_flop_array', name="msf_data_in", columns=self.num_cols,
                                              word_size=self.word_size, align_bitcell=True)

        self.tag_flop_array = self.create_module('tag_flop_array', rows=self.num_rows)
        self.decoder = self.create_module('decoder', rows=self.num_rows)

        self.bitline_buffer_array = SfBitlineBufferArray(word_size=self.num_cols)
        self.add_mod(self.bitline_buffer_array)
        self.bitline_logic_array = SfBitlineLogicArray(word_size=self.word_size)
        self.add_mod(self.bitline_logic_array)
        self.logic_buffers = LogicBuffers()
        self.add_mod(self.logic_buffers)

    def create_module(self, mod_name, *args, **kwargs):
        mod = getattr(self, 'mod_' + mod_name)(*args, **kwargs)
        self.add_mod(mod)
        return mod

    def add_modules(self):
        self.add_bitcell_array()

        self.add_ml_precharge_array()
        self.add_search_sense_amp_array()
        self.add_tag_flops()

        self.add_wordline_and_decoder()

        self.add_bitline_buffers()
        self.add_bitline_logic()

        self.add_data_mask_flops()
        self.add_logic_buffers()

        self.width = self.tag_flop_array_inst.rx()
        self.height = self.bitline_buffer_array_inst.uy() - self.logic_buffers_inst.by()

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        self.bitcell_array_inst = self.add_inst(name="bitcell_array", mod=self.bitcell_array, offset=vector(0, 0))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
            temp.append("ml[{0}]".format(j))
        temp.extend(["gnd"])
        self.connect_inst(temp)

    def add_ml_precharge_array(self):
        self.ml_precharge_array_inst = self.add_inst(name="ml_precharge_array", mod=self.ml_precharge_array,
                                                     offset=vector(self.bitcell_array_inst.rx(), 0))
        temp = [self.prefix + "matchline_chb"]
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        temp.append("vdd")
        self.connect_inst(temp)

    def add_search_sense_amp_array(self):
        self.search_sense_inst = self.add_inst(name="search_sense_amps", mod=self.search_sense_amp_array,
                                               offset=self.ml_precharge_array_inst.lr())
        temp = []
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("search_out[{0}]".format(i))
        temp.append(self.prefix + "sense_amp_en")
        temp.append("search_ref")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def add_tag_flops(self):
        self.tag_flop_array_inst = self.add_inst(name="tag_flop_array", mod=self.tag_flop_array,
                                                 offset=self.search_sense_inst.lr())
        temp = []
        for i in range(self.num_rows):
            temp.append("search_out[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("tag[{0}]".format(i))
            temp.append("tag_bar[{0}]".format(i))
        temp.append(self.prefix + "clk_buf")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def add_row_decoder(self):
        offset = vector(self.decoder_x_offset, -self.decoder.predecoder_height)
        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.decoder, offset=offset)

        temp = []
        for i in range(self.row_addr_size):
            temp.append("ADDR[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out[{0}]".format(j))
        temp.extend([self.prefix + "clk_buf", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_wordline_driver(self):
        """ Wordline Driver """

        # The wordline driver is placed to the right of the main decoder width.
        # This means that it slightly overlaps with the hierarchical decoder,
        # but it shares power rails. This may differ for other decoders later...
        self.wordline_driver_inst = self.add_inst(name="wordline_driver", mod=self.wordline_driver,
                                                  offset=vector(self.wordline_x_offset, 0))

        temp = []
        for i in range(self.num_rows):
            temp.append("dec_out[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("wl[{0}]".format(i))
        temp.append(self.prefix + "wordline_en")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def add_bitline_buffers(self):
        offset = vector(0, 0)
        self.bitline_buffer_array_inst = self.add_inst(name="bitline_buffer", mod=self.bitline_buffer_array,
                                                       offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("bl_val[{0}]".format(i))
            connections.append("br_val[{0}]".format(i))
        for i in range(0, self.bitline_buffer_array.columns, self.words_per_row):
            connections.append("bl[{0}]".format(i))
            connections.append("br[{0}]".format(i))
        connections.extend(["vdd", "gnd"])
        self.connect_inst(connections)

    def add_bitline_logic(self):
        offset = vector(0, 0)
        self.bitline_logic_array_inst = self.add_inst(name="bitline_logic", mod=self.bitline_logic_array, offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("data_in[{0}]".format(i))
            connections.append("data_in_bar[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("mask_in[{0}]".format(i))
            connections.append("mask_in_bar[{0}]".format(i))
        for i in range(0, self.bitline_logic_array.columns, self.bitline_logic_array.words_per_row):
            connections.append("bl_val[{0}]".format(i))
            connections.append("br_val[{0}]".format(i))
        connections.extend([self.prefix + "clk_buf", self.prefix + "write_buf", "vdd", "gnd"])

        self.connect_inst(connections)

    def add_data_mask_flops(self):
        data_connections = []
        mask_connections = []
        for i in range(self.word_size):
            data_connections.append("DATA[{}]".format(i))
            mask_connections.append("MASK[{}]".format(i))
        for i in range(self.word_size):
            data_connections.extend("data_in[{0}] data_in_bar[{0}]".format(i).split())
            mask_connections.extend("mask_in[{0}] mask_in_bar[{0}]".format(i).split())
        clk_power = [self.prefix + "clk_bar", "vdd", "gnd"]
        data_connections.extend(clk_power)
        mask_connections.extend(clk_power)

        offset = self.bitline_buffer_array_inst.ll() - vector(0, self.msf_data_in.height)
        self.data_in_flops_inst = self.add_inst("data_in", mod=self.msf_data_in, offset=offset)
        self.connect_inst(data_connections)

        offset = self.data_in_flops_inst.ll() - vector(0, self.msf_data_in.height)
        self.mask_in_flops_inst = self.add_inst("mask_in", mod=self.msf_data_in, offset=offset)
        self.connect_inst(mask_connections)

    def add_logic_buffers(self):
        offset = self.mask_in_flops_inst.ll() - vector(0, self.logic_buffers.height)
        self.logic_buffers_inst = self.add_inst("logic_buffers", mod=self.logic_buffers, offset=offset)
        connections = ["bank_sel", "clk", "search"]
        connections.extend([self.prefix + x for x in ["clk_buf", "clk_bar", "write_buf", "sense_amp_en", "wordline_en",
                                                      "matchline_chb"]])
        connections.extend(["vdd", "gnd"])
        self.connect_inst(connections)

    @staticmethod
    def get_module_list():
        modules = ["bitcell", "bitcell_array", "wordline_driver", "decoder", "search_sense_amp_array",
                   "ml_precharge_array", "ms_flop_array", "tag_flop_array"]
        return modules

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))

        for pin in ["bank_sel", "clk", "search", "search_ref", "vdd", "gnd"]:
            self.add_pin(pin)
