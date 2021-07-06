#!/usr/bin/env python3
"""
Run a regression test on a basic array
"""

from cam_test_base import CamTestBase


class CamBitcellArrayTest(CamTestBase):

    def test_4x4_array(self):
        a = self.create_class_from_opts("bitcell_array", cols=4, rows=4)
        self.debug.info(1, "Testing 4x4 array for %s using module %s",
                        a.__class__.__name__, a.cell.name)
        self.local_check(a)


CamTestBase.run_tests(__name__)
