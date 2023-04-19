#!/usr/bin/env python3
import os
from one_t_one_s_test_base import TestBase
from binary_delay_optimizer import BinaryDelayOptimizer


class MramDelayOptimizer(BinaryDelayOptimizer):

    def get_simulation_script(self):
        work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        sim_script = "21_mram_simulation_test.py"
        return sim_script, work_dir, None

    def get_first_half_script(self):
        script_name = "mram_precharge_decoder_analyzer.py"
        current_dir = os.path.abspath(os.path.dirname("__file__"))
        return script_name, current_dir, None

    def get_first_write_script(self):
        script_name = "mram_precharge_decoder_analyzer.py"
        current_dir = os.path.abspath(os.path.dirname("__file__"))
        # write_check = self.get_write_evaluator_script()
        return [(script_name, current_dir,
                 ["--operation=first-write"] + self.other_args)]

    def get_first_read_script(self):
        script_name = "mram_precharge_decoder_analyzer.py"
        current_dir = os.path.abspath(os.path.dirname("__file__"))
        read_check = self.get_read_evaluator_script()
        return [read_check, (script_name, current_dir,
                             ["--operation=first-read"] + self.other_args)]

    def get_read_evaluator_script(self):
        script_name = "21_analyze_mram_simulation_test.py"
        current_dir = os.path.abspath(os.path.join(os.path.dirname("__file__"), ".."))
        return script_name, current_dir, ["--skip_write_check"] + self.other_args

    def get_write_evaluator_script(self):
        script_name, current_dir, _ = self.get_read_evaluator_script()
        return script_name, current_dir, ["--skip_read_check"] + self.other_args

    def get_config_file_name(self):
        return f"config_mram_{self.cmd_line_options.mode}_{self.cmd_line_options.tech}.py"

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

    def optimize_second_write(self):
        from globals import OPTS
        success = super().optimize_second_write()
        self.default_write_trigger_delay = self.default_second_write - OPTS.write_settling_time
        return success

    def set_safe_second_write(self):
        from globals import OPTS
        self.write_trigger_delay = 2 * self.default_write_trigger_delay
        self.second_write = self.write_trigger_delay + OPTS.write_settling_time

    def restore_second_write(self, original_value):
        from globals import OPTS
        self.second_write = original_value
        self.write_trigger_delay = self.second_write - OPTS.write_settling_time

    @staticmethod
    def get_timing_params():
        return BinaryDelayOptimizer.get_timing_params() + ["write_trigger_delay"]

    @staticmethod
    def create_parser():
        parser = BinaryDelayOptimizer.create_parser()
        parser.add_argument("-m", "--mode", choices=["1t1s", "1t2s", "2t1s", "2t2s"],
                            default="1t1s")
        return parser


if __name__ == "__main__":
    evaluator = MramDelayOptimizer()
    evaluator.run()
