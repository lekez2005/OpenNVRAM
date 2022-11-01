import numpy as np

from base.design import design
from globals import OPTS
from modules.mram.sotfet.sotfet_control_buffers_optimizer import SotfetControlBuffersOptimizer


class Sotfet1t1sControlBuffersOptimizer(SotfetControlBuffersOptimizer):
    """Optimize br_reset and then bl_reset since bl_reset is optional depending on
        words_per_row"""

    def get_mod_args(self, buffer_mod, size):
        class_name = buffer_mod.__class__.__name__
        if class_name == "BlBrReset":
            name = "bl_br_reset{:.5g}".format(size)
            return {"name": name, "size": size}
        elif class_name == "PrechargeSingleBitline":
            return {"size": size}
        else:
            return super().get_mod_args(buffer_mod, size)

    def add_additional_configs(self, config_keys):
        precharge = self.bank.precharge_array.child_insts[0].mod
        config_keys.append((precharge, "en", "bl", OPTS.max_precharge_size, np.linspace))

        discharge = self.bank.br_precharge_array.child_insts[0].mod
        config_keys.append((discharge, "br_reset", "br", OPTS.max_precharge_size, np.linspace))

    def get_sorted_driver_loads(self):
        """ put bl_reset_buffers at the end so br_reset is optimized first """

        def is_br_reset(x):
            return x["buffer_stages_str"] == "br_reset_buffers"

        driver_loads = list(self.driver_loads.values())
        driver_loads = list(sorted(driver_loads, key=is_br_reset))

        return driver_loads

    @staticmethod
    def get_is_precharge(buffer_stages_str):
        return buffer_stages_str in ["precharge_buffers", "br_reset_buffers"]

    def get_opt_func_map(self):
        funcs = super().get_opt_func_map()
        new_values = {
            "precharge_buffers": self.create_precharge_optimization_func,
            "bl_reset_buffers": self.create_bl_reset_optimization_func,
            "br_reset_buffers": self.create_br_reset_optimization_func
        }
        funcs.update(new_values)
        return funcs

    def create_br_reset_optimization_func(self, driver_params, driver_config,
                                          loads, eval_buffer_stage_delay_slew):
        precharge_array = self.bank.precharge_array
        self.bank.precharge_array = self.bank.br_precharge_array
        # this uses bl as load even though it's optimizing br but that's fine
        # since the optimization result is used for both bl and br and bl load is larger
        opt_func = self.create_precharge_optimization_func(driver_params, driver_config,
                                                           loads, eval_buffer_stage_delay_slew)

        self.bank.precharge_array = precharge_array
        return opt_func

    def create_bl_reset_optimization_func(self, driver_params, driver_config,
                                          loads, eval_buffer_stage_delay_slew):
        design.name_map.remove("precharge_array")
        design.name_map.remove("precharge")
        design.name_map.remove("bl_br_tap")
        array = self.bank.create_module('br_precharge_array', columns=self.bank.num_cols,
                                        size=OPTS.discharge_size)
        bl_reset_cap, _ = array.get_input_cap("bl_reset")
        loads[-1] += bl_reset_cap
        return self.adjust_optimization_loads(loads, eval_buffer_stage_delay_slew)

    def post_process_buffer_sizes(self, stages, buffer_stages_str, parent_mod):
        if buffer_stages_str == "br_reset_buffers":
            OPTS.discharge_size = stages[-1]
            return stages[:-1]
        return super().post_process_buffer_sizes(stages, buffer_stages_str, parent_mod)
