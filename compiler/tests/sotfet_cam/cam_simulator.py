#!/usr/bin/env python
import os
import sys

from cam_test_base import CamTestBase
from globals import OPTS


class CamSimulator(CamTestBase):
    cmos = False

    def setUp(self):
        self.cmos = not sotfet
        super(CamSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def run_commands(self, use_pex=False, num_banks=1):

        from modules.sotfet.sf_cam import SfCam
        from modules.sotfet.cmos.sw_cam import SwCam
        from sf_cam_delay import SfCamDelay
        from sf_cam_dut import SfCamDut

        OPTS.use_pex = use_pex

        OPTS.word_size = word_size
        OPTS.num_words = num_words

        cam_class = SwCam if self.cmos else SfCam

        self.cam = cam_class(word_size=OPTS.word_size, num_words=OPTS.num_words, num_banks=num_banks, name="sram1",
                             words_per_row=OPTS.words_per_row)
        self.cam.sp_write(OPTS.spice_file)

        delay = SfCamDelay(self.cam, spfile=OPTS.spice_file, corner=self.corner, initialize=False)

        delay.trimsp = False

        delay.search_period = 1.8
        delay.write_period = 2.5
        delay.search_duty_cycle = 0.4
        if not self.cmos:
            delay.write_duty_cycle = 0.6
            SfCamDut.is_sotfet = True
            # use larger write voltage for 128
            if word_size > 64:
                delay.write_period = 3.5
                OPTS.vbias_n = 0.9
        else:
            delay.write_duty_cycle = 0.3
            SfCamDut.is_sotfet = False

        delay.slew = OPTS.slew_rate
        delay.setup_time = OPTS.setup_time

        delay.saved_nodes = []

        delay.prepare_netlist()

        delay.write_delay_stimulus()

        delay.stim.run_sim()

    def test_schematic(self):
        OPTS.trim_netlist = False
        OPTS.run_drc = False
        OPTS.run_lvs = False
        OPTS.run_pex = False
        OPTS.separate_vdd = False
        OPTS.verbose_save = True

        OPTS.use_ultrasim = ultrasim
        OPTS.series = series

        if series:
            device_mode = "OR"
        else:
            device_mode = "AND"
        OPTS.configure_sotfet_params(device_mode)

        self.run_commands(use_pex=True)


def check_arg(arg):
    if arg in sys.argv:
        sys.argv.remove(arg)
        return True
    return False


if "cmos" in sys.argv:
    sotfet = False
else:
    sotfet = True

series = check_arg("series")
ultrasim = check_arg("usim")

if sotfet:
    folder_prefix = "scam" if series else "pcam"
else:
    folder_prefix = "cmos"

suffix = ultrasim*"_usim"

word_size = 64
num_words = 64
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "sotfet_cam")
temp_folder = os.path.join(openram_temp, "{}_{}_{}{}".format(folder_prefix, word_size, num_words, suffix))
CamSimulator.temp_folder = temp_folder


CamTestBase.run_tests(__name__)
