import debug
from base.contact import m2m3, m1m2
from base.design import METAL3, METAL2
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.horizontal.pinv_wordline import pinv_wordline
from modules.baseline_sram import BaselineSram


class SotfetMram(BaselineSram):

    def create_bank(self):
        if OPTS.mram == "sotfet":
            self.fixed_controls = ["vref"]
        else:
            self.fixed_controls = ["vclamp"]
        kwargs = {"name": "bank",
                  "word_size": self.word_size,
                  "num_words": self.num_words_per_bank,
                  "words_per_row": self.words_per_row,
                  "num_banks": self.num_banks}
        self.bank = self.create_mod_from_str(OPTS.bank_class, **kwargs)
        self.add_mod(self.bank)

        if self.num_banks == 2:
            debug.info(1, "Creating left bank")
            kwargs["adjacent_bank"] = self.bank
            kwargs["name"] = "left_bank"
            self.left_bank = self.create_mod_from_str(OPTS.bank_class, **kwargs)

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

    def get_decoder_output_offsets(self, bank_inst):
        offsets = []
        for row in range(self.bank.num_rows):
            wordline_in = bank_inst.get_pin("dec_out[{}]".format(row))
            offsets.append(wordline_in.by())
        return offsets

    def route_decoder_outputs(self):

        for i in range(len(self.bank_insts)):
            bank_inst = self.bank_insts[i]
            y_offsets = self.get_decoder_output_offsets(bank_inst)
            for row in range(self.bank.num_rows):
                decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
                rail_offset = y_offsets[row]
                wordline_in = bank_inst.get_pin("dec_out[{}]".format(row))
                if row % 2 == 0:
                    via_offset = vector(decoder_out.lx(), wordline_in.by())
                    self.add_rect(METAL2, offset=decoder_out.ll(),
                                  height=rail_offset - decoder_out.by())
                else:
                    via_offset = vector(decoder_out.lx(), wordline_in.uy() - m2m3.height)
                    self.add_rect(METAL2, offset=decoder_out.ul(),
                                  height=rail_offset - decoder_out.uy())
                vias = [m2m3]
                if isinstance(self.row_decoder.inv, pinv_wordline):
                    vias.append(m1m2)
                for via in vias:
                    self.add_contact(via.layer_stack, offset=via_offset)
                end_x = wordline_in.lx() if i == 0 else wordline_in.rx()
                self.add_rect(METAL3, offset=vector(decoder_out.lx(), rail_offset),
                              width=end_x - decoder_out.lx())

    def join_bank_controls(self):
        if self.single_bank:
            return
        super().join_bank_controls()

        # find lowest control rail to prevent clash
        rails = [getattr(self, x + "_rail") for x in self.control_inputs]
        y_offset = min(rails, key=lambda x: x.by()).by()

        for bank_inst in self.bank_insts:
            control_rails = [getattr(bank_inst.mod, x + "_rail")
                             for x in bank_inst.mod.left_control_rails]
            min_y = min(control_rails, key=lambda x: x.by()).by() + bank_inst.by()
            y_offset = min(y_offset, min_y)

        y_offset -= self.bus_pitch
        for pin_name in self.fixed_controls:
            self.join_control(pin_name, y_offset)

    def add_pins(self):
        super().add_pins()
        self.add_pin_list(self.fixed_controls)

    def copy_layout_pins(self):
        super().copy_layout_pins()
        for pin_name in self.fixed_controls:
            self.copy_layout_pin(self.right_bank_inst, pin_name)
