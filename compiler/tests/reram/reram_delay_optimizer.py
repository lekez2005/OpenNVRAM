#!/usr/bin/env python3

import os

from reram_test_base import ReRamTestBase
import binary_delay_optimizer
from sram_delay_optimizer import SramDelayOptimizer

current_dir = os.path.abspath(os.path.dirname("__file__"))


def format_float(value, width=7, decimals=4):
    format_str = f"{{0:<{width}.{decimals}g}} ns "
    return format_str.format(value)


binary_delay_optimizer.format_float = format_float


class ReramDelayOptimizer(SramDelayOptimizer):
    sim_script = "21_reram_simulation_test.py"
    analysis_script = "21_analyze_reram_simulation_test.py"
    current_dir = os.path.abspath(os.path.dirname("__file__"))

    def get_simulation_script(self):
        sim_script = "21_reram_simulation_test.py"
        return sim_script, current_dir, None

    def get_first_write_script(self):
        script_name = "reram_precharge_decoder_analyzer.py"
        return [(script_name, current_dir,
                 ["--operation=first-write"] + self.other_args)]

    def get_first_read_script(self):
        script_name = "reram_precharge_decoder_analyzer.py"
        read_check = self.get_read_evaluator_script()
        return [read_check, (script_name, current_dir,
                             ["--operation=first-read"] + self.other_args)]

    def get_read_evaluator_script(self):
        script_name = "21_analyze_reram_simulation_test.py"
        return script_name, current_dir, ["--skip_write_check"] + self.other_args

    def get_write_evaluator_script(self):
        script_name, _, _ = self.get_read_evaluator_script()
        return script_name, current_dir, ["--skip_read_check"] + self.other_args

    def get_config_file_name(self):
        return ReRamTestBase.config_template.format(self.cmd_line_options.tech) + ".py"


if __name__ == "__main__":
    evaluator = ReramDelayOptimizer()
    evaluator.run()
