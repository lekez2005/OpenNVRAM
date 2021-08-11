import sys

sys.path.append('..')

from testutils import OpenRamTest


class CamTestBase(OpenRamTest):
    config_template = "config_cam_{}"

    @staticmethod
    def get_words_per_row(*args, **kwargs):
        from shared_decoder.test_base import TestBase
        return TestBase.get_words_per_row(*args, **kwargs)
