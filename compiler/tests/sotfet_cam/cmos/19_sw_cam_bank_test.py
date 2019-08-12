#!/usr/bin/env python3

from cam_test_base import CamTestBase
import debug


class CamBankTest(CamTestBase):

    def test_small_array(self):

        from modules.sotfet.cmos.sw_cam_bank import SwCamBank
        debug.info(1, "Test small array bank")
        a = SwCamBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_check(a)

    def test_large_array(self):
        from modules.sotfet.cmos.sw_cam_bank import SwCamBank
        debug.info(1, "Test large array bank")
        a = SwCamBank(word_size=128, num_words=128, words_per_row=1, name="bank1")
        self.local_check(a)


CamTestBase.run_tests(__name__)
