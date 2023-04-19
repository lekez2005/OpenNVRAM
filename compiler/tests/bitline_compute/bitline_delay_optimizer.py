#!env python3
import argparse
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from test_base import TestBase

from sram_delay_optimizer import SramDelayOptimizer

CMOS = "cmos"
BIT_PARALLEL = "bp"
BIT_SERIAL = "bs"
ONE_T_ONE_S = "1t1s"


class BaseBitlineOptimizer(SramDelayOptimizer):

    def ceil_(self, value):
        return self.ceil_tolerance(value, scale=1)

    def run_simulation(self):
        self.first_write = self.first_read
        self.second_write = self.second_read
        if mode_options.no_sim:
            return SimpleNamespace(returncode=0)
        return super().run_simulation()

    @staticmethod
    def is_failed_output(output):
        keywords = ["failure:", "Incorrect sum", "unsuccessful at"]
        return any(keyword in output for keyword in keywords)

    def optimize_sense_time(self):
        if mode_options.mirrored:
            return True
        return super().optimize_sense_time()

    def optimize_first_half(self):
        print("First Read/Write:")
        self.optimize_first_read()
        self.default_first_read = self.ceil_(self.default_first_read +
                                             self.cmd_line_options.first_write_margin)
        self.default_first_write = self.default_first_read

    def optimize_second_half(self):
        print("Second Read/Write:")
        self.optimize_second_read()
        self.default_second_read = self.ceil_(self.default_second_read)
        self.default_second_write = self.default_second_read

    def finalize_optimization(self):
        print("final:")
        self.reset_timing_from_defaults()
        self.log_timing("final", True)

    def optimize_same_read_write(self):
        self.optimize_first_half()
        self.optimize_second_half()
        print("Sense time")
        self.default_sense_trigger_delay += self.cmd_line_options.second_read_margin
        self.optimize_sense_time()
        self.default_second_write = self.default_second_read

        self.finalize_optimization()


class BitlineOptimizer(BaseBitlineOptimizer):
    sim_script = "21_bitline_simulation_test.py"
    analysis_script = "21_analyze_bl_sram_test.py"
    precharge_analyzer = "bitline_precharge_decoder_analyzer.py"

    def initialize_openram(self):
        from globals import OPTS
        OPTS.serial = mode_options.mode == BIT_SERIAL
        OPTS.sim_rw_only = mode_options.sim_rw_only
        if mode_options.sim_rw_only:
            self.other_args.append("--sim_rw_only")
        if mode_options.mode == BIT_SERIAL:
            self.other_args.append("--mode=serial")
        if mode_options.mode == ONE_T_ONE_S:
            self.other_args.append(f"--mode={ONE_T_ONE_S}")
        super().initialize_openram()

    def get_config_file_name(self):
        return TestBase.config_template.format(self.cmd_line_options.tech) + ".py"

    def get_value_from_existing_data(self, operation_name, attempt_data):
        if operation_name == "trigger_delay":
            param_names = self.get_timing_params()
            return float(attempt_data[2 + param_names.index("sense_trigger_delay")])
        return super().get_value_from_existing_data(operation_name, attempt_data)

    def update_environment_variable(self):
        env_vars = {
            "first_read": self.first_read,
            "first_write": self.first_write,
            "second_read": self.second_read,
            "second_write": self.second_write,
        }
        duty_cycle = self.first_read / (self.first_read + self.second_read)
        if not mode_options.sim_rw_only:
            env_vars["sense_trigger_delay"] = self.sense_trigger_delay
            env_vars["sense_trigger_delay_differential"] = self.sense_trigger_delay
            env_vars["duty_diffb"] = duty_cycle
            env_vars["duty_diff"] = duty_cycle
        else:
            env_vars["sense_trigger_delay_differential"] = self.sense_trigger_delay
            env_vars["duty_diff"] = duty_cycle
        self.set_timing_environment_variable(env_vars)

    def get_log_file_name(self):
        if mode_options.sim_rw_only:
            suffix = "-rw"
        elif mode_options.mode == BIT_SERIAL:
            suffix = "-serial"
        else:
            suffix = "-blc"
        return Path(super().get_log_file_name()).stem + suffix + ".txt"

    def optimize_trigger_delay(self):
        def pre_sim_update(value):
            self.sense_trigger_delay = value

        def post_sim_update(value):
            self.default_sense_trigger_delay = min(self.default_sense_trigger_delay,
                                                   value)

        print("Trigger Delay:")
        start_value = self.default_sense_trigger_delay
        self.reset_timing_from_defaults()
        self.default_sense_trigger_delay = math.inf
        success = self.run_optimization(start_value, "trigger_delay",
                                        pre_sim_update, post_sim_update,
                                        self.get_read_evaluator_script)
        return success

    def optimize_all(self):
        if mode_options.sim_rw_only:
            return self.optimize_same_read_write()

        # blc: first half -> trigger delay -> sense/compute time
        self.cmd_line_options.sense_margin = 0
        self.optimize_first_half()
        self.optimize_trigger_delay()
        self.optimize_sense_time()
        self.default_second_read = self.ceil_(self.default_second_read)
        self.default_second_write = self.default_second_read
        self.finalize_optimization()

    def get_read_evaluator_script(self):
        return self.analysis_script, self.current_dir, None

    def get_first_read_script(self):
        return [(self.precharge_analyzer, self.current_dir,
                 ["--operation=first-read"] + self.other_args)]


class Bitline1t1sOptimizer(BitlineOptimizer):

    # analysis_script = "no_check.py"
    # precharge_analyzer = "no_check.py"

    def get_config_file_name(self):
        return f"config_bl_1t1s_{self.cmd_line_options.tech}.py"

    @staticmethod
    def get_timing_params():
        return SramDelayOptimizer.get_timing_params() + ["write_trigger_delay"]

    def set_timing_environment_variable(self, env_values):
        """Use max of second_read/second_write for second write"""
        # env_values["second_write"] = max(self.second_write, self.second_read)
        env_values["write_trigger_delay"] = self.write_trigger_delay
        super().set_timing_environment_variable(env_values)

    def optimize_all(self):
        from globals import OPTS
        self.default_write_settling_time = OPTS.write_settling_time
        self.write_trigger_is_optimized = False
        super().optimize_all()

    def optimize_trigger_delay(self):
        from globals import OPTS
        # import debug
        # debug.pycharm_debug()
        self.optimize_second_write()
        self.default_write_trigger_delay = self.default_second_write - OPTS.write_settling_time
        self.write_trigger_is_optimized = True
        super().optimize_trigger_delay()

    def get_second_write_update_callbacks(self):
        from globals import OPTS

        def pre_sim_update(value):
            self.second_write = value
            self.write_trigger_delay = value - OPTS.write_settling_time

        def post_sim_update(value):
            self.default_second_write = min(self.second_write, value)
            self.default_write_trigger_delay = (self.default_second_write -
                                                OPTS.write_settling_time)

        return pre_sim_update, post_sim_update, OPTS.write_settling_time


class CmosOptimizer(BaseBitlineOptimizer):
    current_dir = os.path.abspath(os.path.join(os.path.dirname("__file__"), ".."))

    def get_config_file_name(self):
        return f"config_bl_baseline_{self.cmd_line_options.tech}.py"

    def get_simulation_script(self):
        return self.sim_script, self.current_dir, \
            [f"--config={self.config_file}"] + self.other_args

    def get_read_evaluator_script(self):
        return self.analysis_script, self.current_dir, None

    def optimize_all(self):
        self.optimize_same_read_write()

    @staticmethod
    def set_cmos_configuration():
        # set python path
        current_dir = os.path.abspath(os.path.dirname(__file__))
        os.environ["PYTHONPATH"] = current_dir + ":" + os.getenv("PYTHONPATH", "")
        os.environ["SENSE_AMP_MIRRORED"] = str(mode_options.mirrored)
        sim_suffix = os.getenv("SIM_SUFFIX", "")
        if mode_options.mirrored:
            sim_suffix += "_mirrored"
        os.environ["SIM_SUFFIX"] = sim_suffix


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[CMOS, BIT_PARALLEL, BIT_SERIAL, ONE_T_ONE_S], default=CMOS)
    parser.add_argument("--sim_rw_only", action="store_true")
    parser.add_argument("--mirrored", action="store_true")
    parser.add_argument("--no_sim", action="store_true",
                        help="Don't run sim, just for testing optimization steps")
    first_arg = sys.argv[0]
    mode_options, other_args = parser.parse_known_args()
    sys.argv = [first_arg] + other_args

    if mode_options.mode == CMOS:
        CmosOptimizer.set_cmos_configuration()
        evaluator = CmosOptimizer()
    elif mode_options.mode == ONE_T_ONE_S:
        evaluator = Bitline1t1sOptimizer()
    else:
        evaluator = BitlineOptimizer()

    evaluator.run()
