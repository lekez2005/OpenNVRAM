#!/usr/bin/env python3
"""
Run a regression test on a write driver array.
"""

from test_base import TestBase


class SenseAmpArrayTest(TestBase):

    def test_sense_amp(self):
        a = self.create_class_from_opts("sense_amp_array", word_size=64, words_per_row=1)
        self.debug.info(1, "Created %s with mod %s", a.__class__.__name__,
                        a.child_mod)
        self.local_check(a)


TestBase.run_tests(__name__)
