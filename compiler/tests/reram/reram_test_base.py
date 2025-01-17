import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from testutils import OpenRamTest


class ReRamTestBase(OpenRamTest):
    config_template = "config_reram_{}"
    RERAM_MODE = "reram"
    valid_modes = [RERAM_MODE]
