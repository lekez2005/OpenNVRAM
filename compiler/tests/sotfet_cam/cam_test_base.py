import os
import sys

import unittest

sys.path.append('..')

import testutils
from testutils import parse_args


class CamTestBase(testutils.OpenRamTest):
    config_template = "config_sf_cam_{}"

    @staticmethod
    def run_tests(name):
        if name == "__main__":
            if "cmos" in sys.argv:
                script_dir = os.path.dirname(__file__)
                sys.path.append(os.path.join(script_dir, "cmos"))
                CamTestBase.config_template = "config_sw_cam_{}"
                sys.argv.remove("cmos")
            parse_args()
            unittest.main()



