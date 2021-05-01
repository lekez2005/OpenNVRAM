from base.design import design
from characterizer.control_buffers_optimizer import ControlBufferOptimizer
from globals import OPTS


class SotfetControlBuffersOptimizer(ControlBufferOptimizer):
    def extract_wordline_driver_loads(self):
        """Create config for optimizing wordline driver"""

        driver_load = self.extract_wordline_buffer_load(self.bank.wwl_driver, "wwl",
                                                        "wwl_buffers")
        self.driver_loads["wwl_driver"] = driver_load

        driver_load = self.extract_wordline_buffer_load(self.bank.rwl_driver, "rwl",
                                                        "rwl_buffers")
        self.driver_loads["rwl_driver"] = driver_load

    def add_additional_configs(self, config_keys):
        """Add other Buffer stages that need optimization: precharge, wordline buffers"""
        from globals import OPTS
        # add precharge
        precharge = self.bank.precharge_array.child_insts[0].mod
        if OPTS.precharge_bl:
            in_pin = "en"
        else:
            in_pin = "bl_reset"
        config_keys.append((precharge, in_pin, "bl", OPTS.max_precharge_size))

    def get_sorted_driver_loads(self):
        driver_loads = list(self.driver_loads.values())
        # put br_reset_buffers at the end so precharge_en is optimized first
        driver_loads = list(sorted(driver_loads,
                                   key=lambda x: x["buffer_stages_str"] in
                                                 ["br_reset_buffers", "bl_reset_buffers"]))
        return driver_loads

    def get_opt_func_map(self):
        funcs = super().get_opt_func_map()
        funcs.update({
            "br_reset_buffers": self.create_br_reset_optimization_func,
            "bl_reset_buffers": self.create_bl_reset_optimization_func
        })
        return funcs

    def create_bl_reset_optimization_func(self, driver_params, driver_config,
                                          loads, eval_buffer_stage_delay_slew):
        return self.create_bl_br_reset_optimization_func("bl_reset", driver_params,
                                                         driver_config, loads,
                                                         eval_buffer_stage_delay_slew)

    def create_br_reset_optimization_func(self, driver_params, driver_config,
                                          loads, eval_buffer_stage_delay_slew):
        return self.create_bl_br_reset_optimization_func("br_reset", driver_params,
                                                         driver_config, loads,
                                                         eval_buffer_stage_delay_slew)

    def create_bl_br_reset_optimization_func(self, pin_name, driver_params, driver_config,
                                             loads, eval_buffer_stage_delay_slew):
        # add real br_reset load based on already optimized precharge size
        precharge_size = OPTS.precharge_size
        design.name_map.remove("precharge")
        design.name_map.remove("precharge_array")
        precharge_array = self.bank.create_module('precharge_array', columns=self.bank.num_cols,
                                                  size=precharge_size)
        br_reset_cap, _ = precharge_array.get_input_cap(pin_name)
        loads[-1] += br_reset_cap

        penalty = OPTS.buffer_optimization_size_penalty

        def evaluate_delays(stages_list):
            stage_loads = [x for x in loads]
            delays, slew = eval_buffer_stage_delay_slew(stages_list, stage_loads)
            return delays

        def total_delay(stage_list):
            return sum(evaluate_delays(stage_list)) * 1e12 + penalty * sum(stage_list)

        return (total_delay, evaluate_delays), loads
