#!/usr/bin/env python3
"""
Run a regression test on a single transistor column_mux.
"""

from testutils import OpenRamTest
import debug


class SingleLevelColumnMuxArrayTest(OpenRamTest):

    def runTest(self):
        from modules import single_level_column_mux_array
        
        debug.info(1, "Testing sample for 2-way column_mux_array")
        a = single_level_column_mux_array.single_level_column_mux_array(columns=16, word_size=8)
        self.local_check(a)

        debug.info(1, "Testing sample for 4-way column_mux_array")
        a = single_level_column_mux_array.single_level_column_mux_array(columns=16, word_size=4)
        self.local_check(a)

        debug.info(1, "Testing sample for 8-way column_mux_array")
        a = single_level_column_mux_array.single_level_column_mux_array(columns=32, word_size=4)
        self.local_check(a)


OpenRamTest.run_tests(__name__)
