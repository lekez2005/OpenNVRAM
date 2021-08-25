import numpy as np

import debug
from characterizer.control_buffers_optimizer import ControlBufferOptimizer
from globals import OPTS
from modules.cam.cam_bank import CamBank


class CamControlBuffersOptimizer(ControlBufferOptimizer):

    def __init__(self, bank: CamBank):
        self.bank = bank
        super().__init__(bank)

    def optimize_all(self):
        super().optimize_all()
        OPTS.precharge_buffers = OPTS.discharge_buffers

    def post_process_buffer_sizes(self, stages, buffer_stages_str, parent_mod):
        if buffer_stages_str == "ml_buffers":
            OPTS.ml_precharge_size = stages[-1]
            return stages[:-1]
        return super().post_process_buffer_sizes(stages, buffer_stages_str, parent_mod)

    @staticmethod
    def get_is_precharge(buffer_stages_str):
        return buffer_stages_str in ["precharge_buffers", "discharge_buffers"]

    def get_mod_args(self, buffer_mod, size):
        class_name = buffer_mod.__class__.__name__
        if class_name in ["CamPrecharge"]:
            name = "precharge_{:.5g}".format(size)
            args = {"name": name, "size": size,
                    "words_per_row": self.bank.words_per_row}
        elif class_name in ["MatchlinePrecharge"]:
            name = "ml_precharge_{:.5g}".format(size)
            args = {"name": name, "size": size}
        else:
            return super().get_mod_args(buffer_mod, size)
        return args

    def add_additional_configs(self, config_keys):
        """Add other Buffer stages that need optimization: precharge, wordline buffers"""

        # add bitline precharge
        precharge = self.bank.precharge_array.child_insts[0].mod
        config_keys.append((precharge, "discharge", "bl",
                            OPTS.max_precharge_size, np.linspace))
        debug.info(1, "Add optimization config precharge, in_pin = %s out_pin = %s",
                   "discharge", "bl")

        # add matchline precharge
        ml_precharge = self.bank.ml_precharge_array.precharge
        config_keys.append((ml_precharge, "precharge_en_bar", "ml",
                            OPTS.max_precharge_size, np.linspace))
        debug.info(1, "Add optimization config ml_precharge, in_pin = %s out_pin = %s",
                   "precharge_en_bar", "ml")

    def get_opt_func_map(self):
        funcs = super().get_opt_func_map()
        funcs["discharge_buffers"] = self.create_ml_precharge_optimization_func
        return funcs

    def create_ml_precharge_optimization_func(self, driver_params, driver_config,
                                              loads, eval_buffer_stage_delay_slew):

        precharge_cell = self.bank.ml_precharge_array.precharge
        self.precharge_cell = precharge_cell
        precharge_config_key, _, _ = self.get_buffer_mod_key(precharge_cell)
        bitline_in_cap, _ = self.bank.bitcell_array.get_input_cap("ml[0]")
        num_rows = self.bank.num_rows

        return self.create_dynamic_opt_func(config_key=precharge_config_key, loads=loads,
                                            fixed_load=bitline_in_cap, num_elements=num_rows,
                                            eval_buffer_stage_delay_slew=
                                            eval_buffer_stage_delay_slew)
