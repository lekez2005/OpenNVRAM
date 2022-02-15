from modules.mram.sotfet.sotfet_mram import SotfetMram
from modules.sram_power_grid import WordlineVddMixin


class SotfetMram1t1s(WordlineVddMixin, SotfetMram):

    def add_row_decoder(self):
        self.bank.wordline_driver_inst = self.bank.wwl_driver_inst
        super().add_row_decoder()

    def route_power_grid(self):
        self.create_vdd_wordline()
        super().route_power_grid()

    def copy_layout_pins(self):
        super().copy_layout_pins()
        self.copy_layout_pin(self.bank_inst, "vdd_wordline", "vdd_wordline")

