from characterizer.control_buffers_optimizer import ControlBufferOptimizer
from globals import OPTS
from modules.bitline_compute.bitline_alu import BitlineALU
from modules.logic_buffer import LogicBuffer


class BlComputeOptimizer(ControlBufferOptimizer):

    def extract_loads(self):
        super().extract_loads()
        self.extract_alu_clock_loads()

    def extract_control_flop_loads(self):
        control_flop_insts = self.bank.control_flop_insts
        new_flop_insts = [x for x in control_flop_insts
                          if not x[2] == self.bank.dec_en_1_buf_inst]
        self.bank.control_flop_insts = new_flop_insts
        super().extract_control_flop_loads()
        self.bank.control_flop_insts = control_flop_insts

    def get_config_num_stages(self, buffer_mod, buffer_stages_str, buffer_loads):
        if "sr_clk_buffers" == buffer_stages_str:
            return {len(OPTS.sr_clk_buffers)}
        return super().get_config_num_stages(buffer_mod, buffer_stages_str, buffer_loads)

    def extract_alu_clock_loads(self):
        mcc_col, _, _ = BitlineALU.get_mcc_modules()
        _, cap_per_stage = mcc_col.get_input_cap("clk")
        total_cap = cap_per_stage * self.bank.num_cols

        sample_buffer = LogicBuffer(buffer_stages=OPTS.sr_clk_buffers,
                                    height=OPTS.logic_buffers_height)
        buffer_stages_inst = sample_buffer.buffer_inst
        logic_driver_inst = sample_buffer.logic_inst
        config = (buffer_stages_inst, logic_driver_inst, sample_buffer)

        out_pin = "out" if len(OPTS.sr_clk_buffers) % 2 == 0 else "out_inv"
        self.driver_loads["sr_clk_buffers"] = {"loads": [(out_pin, total_cap)],
                                               "config": config,
                                               "buffer_stages_str": "sr_clk_buffers"}
