import sys

sys.path.append('../..')
sys.path.append('..')

import testutils
header = testutils.header


class CamTestBase(testutils.OpenRamTest):
    config_template = "config_fast_cam_{}"



