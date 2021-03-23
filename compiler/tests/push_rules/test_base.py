import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(parent_dir))

import testutils


class TestBase(testutils.OpenRamTest):
    config_template = "config_push_hs_{}"
