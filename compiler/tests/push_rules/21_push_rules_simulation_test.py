#!/usr/bin/env python3
"""
Run a delay test on push rules sram using spectre/hspice
"""
import os

from test_base import TestBase
from simulator_base import SimulatorBase


class PushRulesSimulationTest(TestBase, SimulatorBase):
    PUSH_MODE = "push"
    valid_modes = [PUSH_MODE]

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def get_netlist_gen_class(self):
        import debug
        import subprocess

        from characterizer import SpiceCharacterizer
        from globals import OPTS

        class PushRuleCharacterizer(SpiceCharacterizer):

            def replace_spice_models(self, file_name):
                original_file = self.trim_sp_file
                basename = os.path.splitext(os.path.basename(original_file))[0]
                replacement = os.path.join(os.path.dirname(original_file), basename + ".mod.sp")

                self.trim_sp_file = replacement

                if (os.path.exists(replacement) and
                        os.path.getmtime(replacement) > os.path.getmtime(original_file)):
                    return

                if hasattr(OPTS, "model_replacements"):
                    model_replacements = OPTS.model_replacements
                    sed_patterns = "; ".join(["s/{}/{}/g".format(mod, rep)
                                              for mod, rep in model_replacements])
                    command = ["sed", sed_patterns, original_file]
                    debug.info(1, "Replacing bitcells with command: {}".format(" ".join(command)))
                    with open(replacement, "w") as f:
                        subprocess.run(command, shell=False, stdout=f)

        return PushRuleCharacterizer

    def test_simulation(self):
        self.run_simulation()


if __name__ == "__main__":
    PushRulesSimulationTest.parse_options()
    PushRulesSimulationTest.run_tests(__name__)
