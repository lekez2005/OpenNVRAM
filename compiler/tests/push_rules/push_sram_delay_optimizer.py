#!env python3
import os

from test_base import TestBase
from sram_delay_optimizer import SramDelayOptimizer


class PushSramDelayOptimizer(SramDelayOptimizer):
    sim_script = "21_push_rules_simulation_test.py"
    analysis_script = "21_analyze_push_simulation_test.py"
    current_dir = os.path.abspath(os.path.dirname("__file__"))
    precharge_analyzer = "push_sram_precharge_decoder_analyzer.py"

    def get_config_file_name(self):
        return TestBase.config_template.format(self.cmd_line_options.tech) + ".py"


if __name__ == "__main__":
    evaluator = PushSramDelayOptimizer()
    evaluator.run()
