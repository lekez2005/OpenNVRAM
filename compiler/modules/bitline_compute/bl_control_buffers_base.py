from abc import ABC

from globals import OPTS
from modules.control_buffers import ControlBuffers


class BlControlBuffersBase(ControlBuffers, ABC):
    def get_bank_clocks(self):
        mirror_sense_amp = OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP
        clocks = []
        if self.use_decoder_clk:
            clocks.append("decoder_clk")
            if mirror_sense_amp:
                clocks.append("clk_buf")
        else:
            clocks.append("clk_buf")
        return clocks
