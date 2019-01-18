#!/usr/bin/env python3

from unittest import skipIf


from cam_test_base import CamTestBase
import debug

CamTestBase.initialize_tests(CamTestBase.config_template)
from globals import OPTS


class CamBankTest(CamTestBase):

    @skipIf(not (hasattr(OPTS, "cam_block") and OPTS.cam_block == "cam_block_wwl"), "cam_block_wwl not selected")
    def test_block(self):
        from modules.cam import cam_block_wwl
        debug.info(2, "Create cam block")
        a = cam_block_wwl.cam_block_wwl(word_size=64, num_words=64, words_per_row=1, num_banks=1, name="cam_block")
        self.local_check(a)


CamTestBase.run_tests(__name__)
