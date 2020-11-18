from base.design import METAL2
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.push_rules.horizontal_bank import HorizontalBank
from modules.shared_decoder.cmos_sram import CmosSram


class HorizontalSram(CmosSram):
    rotation_for_drc = GDS_ROT_270
    config_template = "config_push_hs_{}"

    def create_bank(self):
        self.bank = HorizontalBank(name="bank", word_size=self.word_size,
                                   num_words=self.num_words_per_bank,
                                   words_per_row=self.words_per_row, num_banks=self.num_banks)
        self.add_mod(self.bank)
        # self.left_bank = HorizontalBank(name="left_bank", word_size=self.word_sizer,
        #                                 num_words=self.num_words_per_bank,
        #                                 words_per_row=self.words_per_row, num_banks=self.num_banks,
        #                                 is_left_bank=True)
        # self.add_mod(self.left_bank)

    def get_bank_connections(self, bank_num):
        connections = super().get_bank_connections(0)
        bank_sel_index = connections.index("bank_sel")
        other_connections = ["bank_sel", "read", "clk", "sense_trig", "precharge_trig"]
        if bank_num == 0:
            other_connections.extend(["clk_buf", "clk_bar", "vdd", "gnd", "wordline_en"])
        else:
            other_connections.extend(["clk_buf_1", "clk_bar_1", "vdd", "gnd"])
        return connections[:bank_sel_index] + other_connections

    def get_row_decoder_connections(self):
        connections = super().get_row_decoder_connections() + ["wordline_en"]
        return connections

    def add_row_decoder(self):

        left_most_rail_x = self.bank.leftmost_rail.offset.x
        max_predecoder_x = (left_most_rail_x - self.get_wide_space(METAL2) -
                            self.row_decoder.width)
        max_row_decoder_x = self.bank.wordline_driver_inst.lx() - self.row_decoder.row_decoder_width
        x_offset = min(max_predecoder_x, max_row_decoder_x)
        y_offset = (self.bank.bitcell_array_inst.uy() - self.row_decoder.height
                    -self.bank.bitcell.height)
        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.row_decoder,
                                              offset=vector(x_offset, y_offset))

        self.connect_inst(self.get_row_decoder_connections())

    def route_layout(self):
        pass
