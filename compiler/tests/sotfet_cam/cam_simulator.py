
import os

from cam_test_base import CamTestBase
from globals import OPTS


class CamSimulator(CamTestBase):
    cmos = False

    def setUp(self):
        super(CamSimulator, self).setUp()

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

    def replace_temp_folder(self, new_temp):
        if not os.path.exists(new_temp):
            os.makedirs(new_temp)
        OPTS.openram_temp = new_temp
        for attr, file_name in [("spice_file", "temp.sp"), ("pex_spice", "pex.sp"),
                                ("reduced_spice", "reduced.sp"), ("gds_file", "temp.gds")]:
            new_val = os.path.join(new_temp, file_name)
            setattr(OPTS, attr, new_val)

    def run_commands(self, use_pex=False, word_size=64, num_words=64, num_banks=1):
        folder_name = "cmos" if self.cmos else "sotfet"
        temp_folder = os.path.join(OPTS.openram_temp, "{}_{}_{}".format(folder_name, word_size, num_words))
        self.replace_temp_folder(temp_folder)
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

        delay.search_period = 2
        delay.write_period = 3
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
        OPTS.run_lvs = True
        OPTS.run_pex = True
        OPTS.separate_vdd = True
        self.run_commands(use_pex=True)


CamTestBase.run_tests(__name__)