#!/usr/bin/env python3

from test_base import TestBase

from sim_analyzer_test import SimAnalyzerTest


class AnalyzeSimulation(SimAnalyzerTest, TestBase):
    sim_dir_suffix = "shared_simulator"

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeSimulation.parse_options()
    AnalyzeSimulation.run_tests(__name__)
