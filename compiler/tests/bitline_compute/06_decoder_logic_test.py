#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class DecoderLogicTest(TestBase):
    def test_control_buffers(self):
        from modules.bitline_compute.decoder_logic import DecoderLogic
        a = DecoderLogic(num_rows=64)
        a.add_body_taps()
        self.local_check(a)


TestBase.run_tests(__name__)
