import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.append(os.path.abspath(parent_dir))

from test_base import TestBase as MramTestBase


class TestBase(MramTestBase):
    config_template = "config_mram_1t1s_{}"
