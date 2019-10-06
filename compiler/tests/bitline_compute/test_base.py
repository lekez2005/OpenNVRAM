import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(parent_dir)

import testutils
import unittest
from testutils import parse_args


class TestBase(testutils.OpenRamTest):
    config_template = "config_bl_{}"

    @staticmethod
    def run_tests(name):
        if name == "__main__":
            if "baseline" in sys.argv:
                TestBase.config_template = "config_baseline_{}"
                sys.argv.remove("baseline")
            parse_args()
            unittest.main()
