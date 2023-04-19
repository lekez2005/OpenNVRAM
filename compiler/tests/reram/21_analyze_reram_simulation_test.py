#!/usr/bin/env python3

from reram_test_base import ReRamTestBase
from sim_analyzer_test import SimAnalyzerTest
from simulator_base import SimulatorBase


class AnalyzeReramSimulationTest(SimAnalyzerTest, SimulatorBase, ReRamTestBase):
    sim_dir_suffix = "reram"
    RERAM_MODE = "reram"
    valid_modes = [RERAM_MODE]

    def setUp(self):
        super().setUp()
        self.update_global_opts()
        from globals import OPTS

        threshold = 0.5
        thickness_threshold = (OPTS.min_filament_thickness + threshold *
                               (OPTS.max_filament_thickness - OPTS.min_filament_thickness))
        self.analyzer.address_data_threshold = thickness_threshold

    def initialize(self):
        super().initialize()
        self.write_settling_time = 200e-12
        self.read_settling_time = 100e-12

    def get_q_net_and_col(self, address, bit):
        from globals import OPTS
        assert OPTS.num_banks == 1, "Only one bank supported"
        bank = 0
        words_per_row = OPTS.words_per_row
        word_index = address % words_per_row
        col = bit * words_per_row + word_index

        q_net = "v({})".format(self.state_probes[str(address)][bit])
        return bank, col, q_net

    def plot_q_data(self):
        from globals import OPTS
        ax2 = self.ax1.twinx()

        from_t = self.probe_start_time
        to_t = self.probe_end_time

        time, signal = self.sim_data.get_signal_time(self.probe_q_net,
                                                     from_t=from_t, to_t=to_t)

        def scale(x):
            return x / OPTS.filament_scale_factor * 1e9

        ax2.plot(time, scale(signal), ':', label="thickness")

        extension = 0.05 * (OPTS.max_filament_thickness - OPTS.min_filament_thickness)

        ax2.set_ylim([scale(OPTS.min_filament_thickness - extension),
                      scale(OPTS.max_filament_thickness + extension)])
        ax2.set_ylabel("Thickness (nm)")
        ax2.legend()

        import matplotlib.pyplot as plt
        plt.sca(self.ax1)

    def plot_internal_sense_amp(self):
        for label, net in zip(["vdata", "sense_out"], ["vdata", "dout"]):
            self.plot_sig(self.get_plot_probe("sense_amp_array", net),
                          label=label)

        self.plot_sig(self.get_plot_probe("control_buffers", "tri_en",
                                          self.probe_control_bit),
                      label="tri_en")

        # self.plot_sig(self.get_plot_probe("control_buffers", "sample_en_bar",
        #                                   self.probe_control_bit),
        #               label="sample_en_bar")
        # self.plot_sig("vref", label="vref")

    def plot_data_out(self):
        sig_name = self.analyzer.get_probe("dout", bank=None, net=None,
                                           bit=self.probe_control_bit)
        self.plot_sig(sig_name, label="dout")

    def get_read_negation(self):
        return True

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeReramSimulationTest.parse_options()
    AnalyzeReramSimulationTest.run_tests(__name__)
