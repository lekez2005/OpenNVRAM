#!/usr/bin/env python3
"""
Run a regression test on a logic_buffers module.
"""

from test_base import TestBase


class LatchedControlBuffersTest(TestBase):
    latched = True

    def test_latched_control_buffers(self):
        from globals import OPTS
        OPTS.sense_amp_type = OPTS.LATCHED_SENSE_AMP
        OPTS.configure_sense_amps(OPTS)
        from modules.bitline_compute.bl_latched_control_buffers import LatchedControlBuffers
        a = LatchedControlBuffers()
        self.local_check(a)


class MirroredControlBuffersTest(TestBase):
    latched = False

    def test_control_buffers_sense_trig(self):
        from modules.bitline_compute.bl_mirrored_control_buffers import BlMirroredControlBuffers
        a = BlMirroredControlBuffers()
        self.local_check(a)


TestBase.run_tests(__name__)
