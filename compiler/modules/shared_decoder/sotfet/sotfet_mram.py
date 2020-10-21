from base.contact import m2m3
from base.design import METAL3, METAL2
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from modules.shared_decoder.cmos_sram import CmosSram
from modules.shared_decoder.sotfet.sotfet_mram_bank import SotfetMramBank


class SotfetMram(CmosSram):

    def create_bank(self):
        self.bank = SotfetMramBank(name="bank", word_size=self.word_size,
                                   num_words=self.num_words_per_bank,
                                   words_per_row=self.words_per_row,
                                   num_banks=self.num_banks)
        self.add_mod(self.bank)

    def join_decoder_wells(self):
        fill_rects = create_wells_and_implants_fills(
            self.row_decoder.inv,
            self.bank.rwl_driver.logic_buffer.logic_mod)

        decoder_right_x = self.row_decoder_inst.lx() + self.row_decoder.row_decoder_width
        wordline_left = self.right_bank_inst.lx() + self.bank.rwl_driver.en_pin_clearance

        for row in range(self.bank.num_rows):
            for fill_rect in fill_rects:
                if row % 4 in [1, 3]:
                    continue
                if row % 4 == 0:
                    fill_rect = (fill_rect[0], self.row_decoder.inv.height -
                                 fill_rect[2],
                                 self.row_decoder.inv.height - fill_rect[1])
                y_shift = (self.bank.wwl_driver_inst.by() +
                           int(row / 2) * self.row_decoder.inv.height)
                self.add_rect(fill_rect[0], offset=vector(decoder_right_x,
                                                          y_shift + fill_rect[1]),
                              height=fill_rect[2] - fill_rect[1],
                              width=wordline_left - decoder_right_x)

    def route_decoder_outputs(self):
        for row in range(self.bank.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            for i in range(len(self.bank_insts)):
                bank_inst = self.bank_insts[i]
                wordline_in = bank_inst.get_pin("dec_out[{}]".format(row))
                if row % 2 == 0:
                    self.add_contact(m2m3.layer_stack,
                                     offset=vector(decoder_out.lx(), wordline_in.by()))
                    self.add_rect(METAL2, offset=decoder_out.ll(),
                                  height=wordline_in.by() - decoder_out.by())
                else:
                    self.add_contact(m2m3.layer_stack,
                                     offset=vector(decoder_out.lx(),
                                                   wordline_in.uy() - m2m3.height))
                    self.add_rect(METAL2, offset=decoder_out.ul(),
                                  height=wordline_in.by() - decoder_out.uy())
                end_x = wordline_in.lx() if i == 0 else wordline_in.rx()
                self.add_rect(METAL3, offset=vector(decoder_out.lx(), wordline_in.by()),
                              width=end_x - decoder_out.lx())

    def get_bank_connections(self, bank_num):
        connections = super().get_bank_connections(bank_num)
        connections.append("vref")
        return connections

    def add_pins(self):
        super().add_pins()
        self.add_pin("vref")

    def copy_layout_pins(self):
        super().copy_layout_pins()
        self.copy_layout_pin(self.right_bank_inst, "vref")
