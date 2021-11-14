#!/usr/bin/env python3

from sotfet_cam_simulator_base import SotfetCamSimulatorBase


class SimulatorSotfetCam(SotfetCamSimulatorBase):

    def test_simulation(self):
        self.run_simulation()


if __name__ == "__main__":
    SimulatorSotfetCam.parse_options()
    SimulatorSotfetCam.run_tests(__name__)
