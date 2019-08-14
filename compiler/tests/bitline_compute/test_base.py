import sys

sys.path.append('..')

import testutils


class TestBase(testutils.OpenRamTest):
    config_template = "config_bl_{}"
