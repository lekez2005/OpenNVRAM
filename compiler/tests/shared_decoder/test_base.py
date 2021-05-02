import math
import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(os.path.abspath(parent_dir))

import testutils
import unittest
from testutils import parse_args


class TestBase(testutils.OpenRamTest):
    config_template = "config_shared_baseline_{}"

    @staticmethod
    def get_words_per_row(num_cols, words_per_row, word_size=32):
        """Assumes 32 bit word size"""
        if words_per_row is not None:
            if isinstance(words_per_row, list):
                return words_per_row
            else:
                return [words_per_row]
        max_col_address_size = int(math.log(num_cols, 2) - math.log(word_size, 2))
        return [int(2 ** x) for x in range(max_col_address_size + 1)]

    @staticmethod
    def run_tests(name):
        if name == "__main__":
            TestBase.baseline = False
            if "sot" in sys.argv:
                TestBase.config_template = "config_shared_sot_{}"
            elif "sotfet" in sys.argv:
                TestBase.config_template = "config_shared_sotfet_{}"
            elif "push" in sys.argv:
                TestBase.config_template = "config_push_hs_{}"
                sys.path.append(os.path.abspath(os.path.join(parent_dir, "push_rules")))
            else:
                TestBase.baseline = True

            parse_args()
            unittest.main()
