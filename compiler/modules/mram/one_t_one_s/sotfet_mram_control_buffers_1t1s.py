from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class SotfetMramControlBuffers1t1s(SotfetMramControlBuffers):
    def extract_precharge_inputs(self):
        self.has_precharge_bl = self.has_bl_reset = self.has_br_reset = True
