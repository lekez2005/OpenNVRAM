from modules.shared_decoder.sotfet.sotfet_mram import SotfetMram


class SotfetMram1t1s(SotfetMram):
    def add_pins(self):
        super().add_pins()
        self.add_pin("rw")

    def join_bank_controls(self):
        super().join_bank_controls()
        self.copy_layout_pin(self.bank_insts[0], "rw")
