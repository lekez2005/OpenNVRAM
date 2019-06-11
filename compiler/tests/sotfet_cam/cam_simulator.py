#!/usr/bin/env python

from cam_test_base import CamTestBase
from globals import OPTS


class CamSimulator(CamTestBase):

    def setUp(self):
        super(CamSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def run_commands(self, use_pex=False, word_size=64, num_words=64, num_banks=1):
        from modules.sotfet.sf_cam import SfCam
        from sf_cam_delay import SfCamDelay

        OPTS.use_pex = use_pex

        OPTS.word_size = word_size
        OPTS.num_words = num_words

        self.cam = SfCam(word_size=OPTS.word_size, num_words=OPTS.num_words, num_banks=num_banks, name="cam",
                         words_per_row=OPTS.words_per_row)
        self.cam.sp_write(OPTS.spice_file)
        self.cam.gds_write(OPTS.gds_file)

        delay = SfCamDelay(self.cam, spfile=OPTS.spice_file, corner=self.corner, initialize=False)

        delay.trimsp = False

        delay.search_period = 1
        delay.write_period = 2
        delay.search_duty_cycle = 0.3
        delay.write_duty_cycle = 0.15

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()

        delay.write_delay_stimulus()
        delay.stim.run_sim()

    def test_schematic(self):
        OPTS.trim_netlist = False
        self.run_commands()


CamTestBase.run_tests(__name__)
