#!/usr/bin/env python3
import re

from test_base import TestBase

from sim_analyzer_test import SimAnalyzerTest


class AnalyzePushSimulationTest(SimAnalyzerTest, TestBase):
    PUSH_MODE = "push"
    valid_modes = [PUSH_MODE]
    ws = None

    def initialize(self):
        super().initialize()
        from globals import OPTS
        if OPTS.use_pex:
            self.read_settling_time = 50e-12
        else:
            self.read_settling_time = 0e-12

    def create_analyzer(self):
        from characterizer.simulation.sim_analyzer import SimAnalyzer

        class PushAnalyzer(SimAnalyzer):
            def get_probe(self, probe_key, net, bank=None, col=None, bit=None):
                if probe_key in ["sense_amp_array"] and not net.endswith("<0>"):
                    net = f"{net}<0>"
                return super().get_probe(probe_key, net, bank, col, bit)

        self.analyzer = PushAnalyzer(self.temp_folder)

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzePushSimulationTest.parse_options()
    AnalyzePushSimulationTest.run_tests(__name__)
