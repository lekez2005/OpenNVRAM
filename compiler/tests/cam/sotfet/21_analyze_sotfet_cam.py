#!/usr/bin/env python3

from sotfet_cam_simulator_base import SotfetCamSimulatorBase
from cam_analyzer import CamAnalyzer


class AnalyzeSotfetCam(CamAnalyzer, SotfetCamSimulatorBase):
    def setUp(self):
        super().setUp()
        self.read_settling_time = self.search_settling_time = 200e-12
        self.write_settling_time = 250e-12

    def plot_read_signals(self):
        super().plot_read_signals()
        self.plot_sig(self.get_plot_probe("search_sense_amps", "vin_int", bit=self.probe_row),
                      label=f"vin_int[{self.probe_row}]")
        self.plot_sig(self.get_plot_probe("search_sense_amps", "vcomp_int", bit=self.probe_row),
                      label=f"vcomp_int[{self.probe_row}]")

    def test_analysis(self):
        self.analyze()

    def plot_write_signals(self):
        super().plot_write_signals()
        self.plot_mram_current()

    def get_read_negation(self):
        from globals import OPTS
        return OPTS.sotfet_cam_mode == "pcam"

    def get_write_negation(self):
        from globals import OPTS
        return OPTS.sotfet_cam_mode == "pcam"


if __name__ == "__main__":
    AnalyzeSotfetCam.parse_options()
    AnalyzeSotfetCam.run_tests(__name__)
