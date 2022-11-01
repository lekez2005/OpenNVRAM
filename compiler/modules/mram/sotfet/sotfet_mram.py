import debug
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.baseline_sram import BaselineSram
from modules.sram_mixins import StackedDecoderMixin


class SotfetMram(StackedDecoderMixin, BaselineSram):

    def create_bank(self):
        kwargs = {"name": "bank",
                  "word_size": self.word_size,
                  "num_words": self.num_words_per_bank,
                  "words_per_row": self.words_per_row,
                  "num_banks": self.num_banks}
        self.bank = self.create_mod_from_str(OPTS.bank_class, **kwargs)
        self.add_mod(self.bank)

        self.fixed_controls = []
        for pin_name in ["vref", "vclamp"]:
            if pin_name in self.bank.pins:
                self.fixed_controls.append(pin_name)

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

    def copy_layout_pins(self):
        super().copy_layout_pins()
        for pin_name in self.fixed_controls:
            self.copy_layout_pin(self.right_bank_inst, pin_name)
