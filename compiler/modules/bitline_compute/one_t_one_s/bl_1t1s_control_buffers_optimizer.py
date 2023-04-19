from characterizer.control_buffers_optimizer import ControlBufferOptimizer
from globals import OPTS
from modules.bitline_compute.bl_compute_optimizer import BlComputeOptimizerMixin
from modules.mram.sotfet.sotfet_control_buffers_optimizer import SotfetControlBuffersOptimizer


class Bl1t1sControlBuffersOptimizer(BlComputeOptimizerMixin, SotfetControlBuffersOptimizer):

    def calculate_size_penalty(self, stages, buffer_stages_str):
        penalty = OPTS.buffer_optimization_size_penalty
        return penalty * sum(stages)

    def add_additional_configs(self, config_keys):
        ControlBufferOptimizer.add_additional_configs(self, config_keys)

    def extract_col_decoder_loads(self):
        # optimize using flop buffer
        parent_mod = self.bank.control_flop_insts[0][2].mod
        buffer_stages_inst = parent_mod.buffer_inst

        driver_inst = parent_mod.flop_inst
        config = (buffer_stages_inst, driver_inst, parent_mod)

        sel_in_cap, _ = self.bank.write_driver_array.get_input_cap("bl_sel")
        driver_load = {
            "loads": [("out", sel_in_cap), ("out_inv", sel_in_cap)],
            "config": config,
            "buffer_stages_str": "column_decoder_buffers"
        }
        self.driver_loads["col_decoder"] = driver_load
