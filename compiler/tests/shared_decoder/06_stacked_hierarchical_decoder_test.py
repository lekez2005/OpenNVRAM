#!/usr/bin/env python3
"""
Run a regression test on a stacked hierarchical decoder.
"""

from test_base import TestBase


class StackedHierarchicalDecoderTest(TestBase):
    def test_all_row_decoders(self):
        from globals import OPTS
        from modules.shared_decoder.sotfet.stacked_hierarchical_decoder \
            import stacked_hierarchical_decoder
        OPTS.decoder_flops = True
        for row in [32, 64, 128, 256, 512]:
            decoder = stacked_hierarchical_decoder(row)
            self.local_check(decoder)


TestBase.run_tests(__name__)
