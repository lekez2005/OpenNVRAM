from characterizer.control_buffers_optimizer import ControlBufferOptimizer


class BlComputeOptimizer(ControlBufferOptimizer):
    def extract_control_flop_loads(self):
        control_flop_insts = self.bank.control_flop_insts
        new_flop_insts = [x for x in control_flop_insts
                          if not x[2] == self.bank.dec_en_1_buf_inst]
        self.bank.control_flop_insts = new_flop_insts
        super().extract_control_flop_loads()
        self.bank.control_flop_insts = control_flop_insts
