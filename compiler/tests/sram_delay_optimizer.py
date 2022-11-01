#!env python3
import os

from testutils import OpenRamTest

from binary_delay_optimizer import BinaryDelayOptimizer


class SramDelayOptimizer(BinaryDelayOptimizer):
    sim_script = "21_simulation_test.py"
    analysis_script = "21_analyze_simulation_test.py"
    precharge_analyzer = "sram_precharge_decoder_analyzer.py"
    current_dir = os.path.abspath(os.path.dirname("__file__"))

    def get_simulation_script(self):
        return self.sim_script, self.current_dir, None

    def get_read_evaluator_script(self):
        return self.analysis_script, self.current_dir, \
               ["--skip_write_check"] + self.other_args

    def get_write_evaluator_script(self):
        return self.analysis_script, self.current_dir, \
               ["--skip_read_check"] + self.other_args

    def get_first_write_script(self):
        return ([self.get_write_evaluator_script()] +
                [(self.precharge_analyzer, self.current_dir,
                  ["--operation=first-write"] + self.other_args)])

    def get_first_read_script(self):
        return [(self.precharge_analyzer, self.current_dir,
                 ["--operation=first-read"] + self.other_args)]

    def get_config_file_name(self):
        return OpenRamTest.config_template.format(self.cmd_line_options.tech) + ".py"


if __name__ == "__main__":
    evaluator = SramDelayOptimizer()
    evaluator.run()
