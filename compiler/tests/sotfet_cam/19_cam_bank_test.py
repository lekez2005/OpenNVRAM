#!/usr/bin/env python3

from cam_test_base import CamTestBase
from unittest import skipIf
import debug


class CamBankTest(CamTestBase):

    @skipIf(False, "Skip small array test")
    def test_small_array(self):

        from modules.sotfet import sf_cam_bank
        debug.info(1, "Test small array bank")
        a = sf_cam_bank.SfCamBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_check(a)

    @skipIf(True, "Skip large array test")
    def test_large_array(self):
        from modules.sotfet import sf_cam_bank
        a = sf_cam_bank.SfCamBank(word_size=256, num_words=256, words_per_row=1, name="bank1")
        self.local_check(a)


CamTestBase.run_tests(__name__)
