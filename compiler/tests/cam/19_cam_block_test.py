#!/usr/bin/env python3

from unittest import skipIf

from cam_test_base import CamTestBase

CamTestBase.initialize_tests(CamTestBase.config_template)

from globals import OPTS


class CamBankTest(CamTestBase):

    @skipIf(not (hasattr(OPTS, "cam_block") and OPTS.cam_block == "cam_block"), "Cam block not selected")
    def test_block(self):
        from modules.cam import cam_block
        self.debug.info(2, "Create cam block")
        a = cam_block.cam_block(word_size=128, num_words=64, words_per_row=1, num_banks=1, name="cam_block")
        self.local_check(a)


CamTestBase.run_tests(__name__)
