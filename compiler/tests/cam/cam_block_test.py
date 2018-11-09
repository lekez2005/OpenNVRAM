#!/usr/bin/env python2.7

from cam_test_base import CamTestBase, run_tests

import debug


class CamBankTest(CamTestBase):

    def test_block(self):
        from modules.cam import cam_block
        debug.info(2, "Create cam block")
        a = cam_block.CamBlock(word_size=128, num_words=64, words_per_row=1, num_banks=1, name="cam_block")
        self.local_check(a)


run_tests(__name__)
