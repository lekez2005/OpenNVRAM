#!/usr/bin/env python3
"""
Run a regression test on a write driver array
"""

from testutils import OpenRamTest
import debug


class WriteDriverTest(OpenRamTest):

    def runTest(self):
        from modules import write_driver_array

        debug.info(2, "Testing write_driver_array for columns=8, word_size=8")
        a = write_driver_array.write_driver_array(columns=8, word_size=8)
        self.local_check(a)

        debug.info(2, "Testing write_driver_array for columns=16, word_size=8")
        a = write_driver_array.write_driver_array(columns=16, word_size=8)
        self.local_check(a)
        

OpenRamTest.run_tests(__name__)
