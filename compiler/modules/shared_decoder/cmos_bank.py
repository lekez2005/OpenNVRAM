from globals import OPTS
from modules.baseline_bank import BaselineBank


class CmosBank(BaselineBank):

    def create_control_buffers(self):
        if OPTS.baseline:
            if self.words_per_row == 1:
                from modules.shared_decoder.control_buffers_no_col_mux import LatchedControlBuffers
            else:
                from modules.baseline_latched_control_buffers import LatchedControlBuffers
        else:
            from modules.bitline_compute.bl_latched_control_buffers import LatchedControlBuffers
        self.control_buffers = LatchedControlBuffers()
        self.add_mod(self.control_buffers)
