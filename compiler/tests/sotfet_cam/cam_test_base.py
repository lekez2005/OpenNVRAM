import sys

sys.path.append('..')

import testutils
header = testutils.header


class CamTestBase(testutils.OpenRamTest):
    config_template = "config_sf_cam_{}"



