#!/usr/bin/env python3
"""
Analyze mram simulation for correctness
"""
from mram_simulator import MramSimulator

from sim_analyzer_test import SimAnalyzerTest
from test_base import TestBase


class AnalyzeMramSimulation(MramSimulator, SimAnalyzerTest, TestBase):

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def get_wordline_en_delay(self):
        probes = self.voltage_probes["control_buffers"][str(self.probe_bank)]["rwl_en"]
        max_row = max(map(int, probes.keys()))
        return self.voltage_probe_delay("control_buffers", "rwl_en", self.probe_bank,
                                        bit=max_row, edge=self.RISING_EDGE)

    def plot_internal_sense_amp(self):
        for net in ["dout_bar"]:
            self.plot_sig(self.get_plot_probe("sense_amp_array", net),
                          label=net)

    def get_read_negation(self):
        return True

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeMramSimulation.parse_options()
    AnalyzeMramSimulation.run_tests(__name__)
