#!/usr/bin/env python3
"""
Run a delay test on cam using spice simulator
"""
from cam_test_base import CamTestBase
from cam_simulator import CamSimulator


class CamSimulationTest(CamSimulator, CamTestBase):
    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def test_simulation(self):
        self.run_simulation()


if __name__ == "__main__":
    CamSimulationTest.parse_options()
    CamSimulationTest.run_tests(__name__)
