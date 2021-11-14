#!/usr/bin/env python3

from cam_test_base import CamTestBase
from cam_analyzer import CamAnalyzer
from cam_simulator import CamSimulator


class AnalyzeCamSimulationTest(CamAnalyzer, CamSimulator, CamTestBase):
    def setUp(self):
        super().setUp()
        self.update_global_opts()
        self.read_settling_time = self.search_settling_time = 100e-12
        self.write_settling_time = 250e-12

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeCamSimulationTest.parse_options()
    AnalyzeCamSimulationTest.run_tests(__name__)
