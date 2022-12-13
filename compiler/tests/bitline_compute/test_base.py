import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(parent_dir)

import testutils
import unittest
from testutils import parse_args


class TestBase(testutils.OpenRamTest):
    config_template = "config_bl_{}"

    def setUp(self):
        super().setUp()
        from globals import OPTS
        OPTS.serial = getattr(self, "serial", False)

        if getattr(self, "latched", True):
            OPTS.sense_amp_type = OPTS.LATCHED_SENSE_AMP
        else:
            OPTS.sense_amp_type = OPTS.MIRROR_SENSE_AMP

        OPTS.configure_modules(None, OPTS)

    @staticmethod
    def run_tests(name):
        if name == "__main__":
            if "baseline" in sys.argv:
                TestBase.baseline = True
                TestBase.config_template = "config_bl_baseline_{}"
                sys.argv.remove("baseline")
            elif "serial" in sys.argv:
                TestBase.serial = True
                sys.argv.remove("serial")
            if "mirrored" in sys.argv:
                TestBase.latched = False
                sys.argv.remove("mirrored")
            parse_args()
            unittest.main()
