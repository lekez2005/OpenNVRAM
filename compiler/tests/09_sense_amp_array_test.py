#!/usr/bin/env python3
"""
Run a regression test on a sense amp array
"""

from testutils import OpenRamTest
import debug


class SenseAmpTest(OpenRamTest):

    def runTest(self):
        from modules import sense_amp_array

        debug.info(2, "Testing sense_amp_array for word_size=8, words_per_row=1")
        a = sense_amp_array.sense_amp_array(word_size=8, words_per_row=1)
        self.local_check(a)

        debug.info(2, "Testing sense_amp_array for word_size=4, words_per_row=2")
        a = sense_amp_array.sense_amp_array(word_size=4, words_per_row=2)
        self.local_check(a)

        debug.info(2, "Testing sense_amp_array for word_size=4, words_per_row=4")
        a = sense_amp_array.sense_amp_array(word_size=4, words_per_row=4)
        self.local_check(a)
        

OpenRamTest.run_tests(__name__)
