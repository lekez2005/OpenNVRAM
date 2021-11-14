import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from testutils import OpenRamTest


class CamTestBase(OpenRamTest):
    config_template = "config_cam_{}"

    @staticmethod
    def get_words_per_row(*args, **kwargs):
        from mram.test_base import TestBase
        return TestBase.get_words_per_row(*args, **kwargs)
