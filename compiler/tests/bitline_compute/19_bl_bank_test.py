#!/usr/bin/env python3

from test_base import TestBase
import debug


class BlBankTest(TestBase):

    def test_array(self):

        from modules.bitline_compute.bl_bank import BlBank
        debug.info(1, "Test bitline compute single bank")
        a = BlBank(word_size=64, num_words=64, words_per_row=1, name="bank1")
        self.local_check(a)


TestBase.run_tests(__name__)
