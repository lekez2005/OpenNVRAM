import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(os.path.abspath(parent_dir))

import testutils
import unittest
from testutils import parse_args


class TestBase(testutils.OpenRamTest):
    config_template = "config_mram_sotfet_{}"

    @staticmethod
    def run_tests(name):
        if name == "__main__":
            if "sot" in sys.argv:
                TestBase.config_template = "config_mram_sot_{}"
            elif "sotfet" in sys.argv:
                TestBase.config_template = "config_mram_sotfet_{}"
            parse_args()
            unittest.main()
