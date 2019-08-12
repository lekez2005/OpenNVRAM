#!/usr/bin/env python3
"""
Run a regression test on a hierarchical decoder.
"""

from cam_test_base import CamTestBase


class HierarchicalDecoderTest(CamTestBase):
    def test_32_row_decoder(self):
        from globals import OPTS
        from modules.hierarchical_decoder import hierarchical_decoder
        OPTS.decoder_flops = False
        decoder = hierarchical_decoder(32)
        self.local_drc_check(decoder)


CamTestBase.run_tests(__name__)
