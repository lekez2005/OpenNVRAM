#!/usr/bin/env python3

from cam_test_base import CamTestBase
import debug


class CamBankTest(CamTestBase):

    def test_small_array(self):
        from modules.cam import cam_bank
        debug.info(1, "Test small array bank")
        a = cam_bank.CamBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_check(a)

    def test_large_array(self):
        from modules.cam import cam_bank
        debug.info(1, "No column mux")
        a = cam_bank.CamBank(word_size=256, num_words=512, words_per_row=1, name="bank1")
        self.local_check(a)


CamTestBase.run_tests(__name__)
