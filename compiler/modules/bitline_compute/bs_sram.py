from modules.bitline_compute.bit_serial_alu import BitSerialALU
from modules.bitline_compute.bl_sram import BlSram


class BsSram(BlSram):

    def create_alu(self):
        self.alu = BitSerialALU(bank=self.bank, num_cols=self.num_cols)
        self.add_mod(self.alu)
