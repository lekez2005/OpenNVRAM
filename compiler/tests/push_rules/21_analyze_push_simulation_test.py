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
        self.read_settling_time = 100e-12

    def create_analyzer(self):
        from characterizer.simulation.sim_analyzer import SimAnalyzer

        class PushAnalyzer(SimAnalyzer):
            def get_probe(self, probe_key, net, bank=None, col=None, bit=None):
                if probe_key in ["sense_amp_array"] and not net.endswith("<0>"):
                    net = f"{net}<0>"
                return super().get_probe(probe_key, net, bank, col, bit)

        self.analyzer = PushAnalyzer(self.temp_folder)

    def test_analysis(self):
        self.use_matplotlib = False
        self.new_plot = False
        self.clear_plot = True
        self.load_cadence()
        self.analyze()

    def load_cadence(self):
        if self.cmd_line_opts.plot is None:
            return
        if self.ws is not None:
            return
        from matplotlib import pyplot as plt

        def noop(*args, **kwargs):
            pass

        plt.show = noop
        plt.legend = noop

        from skillbridge import Workspace
        self.ws = Workspace.open()
        if self.new_plot:
            self.skill_plot_id = self.ws.awv.create_plot_window()
        else:
            self.skill_plot_id = self.ws.awv.get_current_window()
        # print(self.skill_plot_id)
        if self.skill_plot_id is None:
            self.skill_plot_id = self.ws.awv.create_plot_window()
        if self.clear_plot:
            self.ws.awv.clear_plot_window(self.skill_plot_id)
        assert self.ws.rdb.set_current_directory("unbound", self.temp_folder), \
            "Loading Cadence results failed"

    def run_plots(self):
        super().run_plots()
        if self.cmd_line_opts.plot is None:
            return
        from_t = self.probe_start_time
        to_t = self.probe_end_time
        self.ws.awv.zoom_graph_x(self.skill_plot_id, [from_t, to_t])

    @staticmethod
    def get_plot_name(signal_name):
        from globals import OPTS
        if OPTS.use_pex:
            plot_name = signal_name
            for prefix in ["_Xbank[0-9]+", "Xrow_decoder"]:
                if len(re.findall(prefix, plot_name)) == 2:
                    plot_name = re.split(prefix, plot_name)[1]
                plot_name = re.split(prefix, plot_name)[0]
            if plot_name.startswith("v("):
                plot_name = plot_name[2:]
            if plot_name.startswith("_"):
                plot_name = plot_name[1:]

            plot_name = plot_name.replace("Xsram.N_", "")
            plot_name = plot_name.split("_X")[-1]
        else:
            plot_name = signal_name.split(".")[-1].replace(")", "")
        return plot_name

    def plot_sig(self, signal_name, label, from_t=None, to_t=None):

        if self.use_matplotlib:
            return super().plot_sig(signal_name, label, from_t, to_t)

        from sim_analyzer_test import plot_exclusions
        if signal_name is None:
            return

        for excl in plot_exclusions:
            if excl in signal_name:
                return
        try:
            self.debug.print_str(signal_name)
            real_signal_name = self.sim_data.convert_signal_name(signal_name)
            if real_signal_name is None:
                print("Signal {} not found".format(signal_name))
                return
            plot_expression = f"v(\"{real_signal_name}\", ?result \"tran-tran\" ?resultsDir \"{self.temp_folder}\")"
            plot_name = self.get_plot_name(real_signal_name)
            # self.ws.awv.simple_plot_expression(self.skill_plot_id, f"VT(\"vdd\"", None, None, expr=["vdd3"])

            return self.ws.awv.simple_plot_expression(self.skill_plot_id, plot_expression, None, None,
                                                      expr=[plot_name])

        except ValueError as er:
            print(er)


if __name__ == "__main__":
    AnalyzePushSimulationTest.parse_options()
    AnalyzePushSimulationTest.run_tests(__name__)
