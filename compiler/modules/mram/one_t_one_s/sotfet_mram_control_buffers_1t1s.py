from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class SotfetMramControlBuffers1t1s(SotfetMramControlBuffers):
    def extract_precharge_inputs(self):
        self.one_wpr = self.bank.words_per_row == 1
        self.has_precharge_bl = self.has_br_reset = True
        self.has_bl_reset = not self.one_wpr
