#!/usr/bin/env python3
from unittest import skipIf

from cam_test_base import CamTestBase
import debug


class CamBankTest(CamTestBase):

    @skipIf(False, "Skip small array test")
    def test_small_array(self):

        from modules.sotfet.cmos.sw_cam_bank import SwCamBank
        debug.info(1, "Test small array bank")
        # a = SwCamBank(word_size=34, num_words=32, words_per_row=1, name="bank1")
        # a = SwCamBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        a = SwCamBank(word_size=128, num_words=128, words_per_row=1, name="bank1")
        self.local_check(a)

    @skipIf(True, "Skip large array test")
    def test_large_array(self):
        from modules.sotfet.cmos.sw_cam_bank import SwCamBank
        debug.info(1, "Test large array bank")
        a = SwCamBank(word_size=128, num_words=128, words_per_row=1, name="bank1")
        self.local_check(a)


CamTestBase.run_tests(__name__)
