#!/usr/bin/env python3
"""
Analyze mram simulation for correctness
"""

from test_base import TestBase
from mram_simulator import MramSimulator
from sim_analyzer_test import SimAnalyzerTest, print_max_delay


class AnalyzeMramSimulation(MramSimulator, SimAnalyzerTest, TestBase):

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def initialize(self):
        super().initialize()
        from globals import OPTS
        if OPTS.mram == "sot":
            self.read_settling_time = 200e-12
        else:
            self.read_settling_time = 200e-12
        self.write_settling_time = 200e-12

    def plot_write_signals(self):
        super().plot_write_signals()
        self.plot_mram_current()

    def print_wordline_en_delay(self):
        probes = self.voltage_probes["control_buffers"][str(self.probe_bank)]["rwl_en"]
        max_row = max(map(int, probes.keys()))
        delay = self.voltage_probe_delay("control_buffers", "rwl_en", self.probe_bank,
                                         bit=max_row, edge=self.RISING_EDGE)
        print_max_delay("Wordline EN", delay)

    def get_wordline_en_delay(self):
        probes = self.voltage_probes["control_buffers"][str(self.probe_bank)]["rwl_en"]
        max_row = max(map(int, probes.keys()))
        return self.voltage_probe_delay("control_buffers", "rwl_en", self.probe_bank,
                                        bit=max_row, edge=self.RISING_EDGE)

    def plot_internal_sense_amp(self):
        from globals import OPTS
        internal_nets = ["dout_bar", "vref"]
        if OPTS.mram == "sot":
            internal_nets.append("vdata")
        for net in internal_nets:
            self.plot_sig(self.get_plot_probe("sense_amp_array", net),
                          label=net)

    def get_wl_name(self):
        if self.cmd_line_opts.plot == "write":
            return "wwl"
        return "wl"

    def get_read_negation(self):
        return True

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeMramSimulation.parse_options()
    AnalyzeMramSimulation.run_tests(__name__)
