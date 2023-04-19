#!env python3
"""
Test level-shifted wordline driver
"""
from reram_test_base import ReRamTestBase


class LevelShiftWordlineDriverTest(ReRamTestBase):
    def test_single_driver(self):
        """Test standalone wordline driver"""
        from modules.reram.level_shift_wordline_driver_array import LevelShiftWordlineDriver
        from globals import OPTS
        height = self.create_class_from_opts("bitcell").height * 2

        buffer_stages = OPTS.wordline_buffers
        driver = LevelShiftWordlineDriver(buffer_stages=buffer_stages, logic="pnand2",
                                          height=height)
        self.local_check(driver)

    def test_driver_array(self):
        """Test wordline array"""
        from modules.reram.level_shift_wordline_driver_array import LevelShiftWordlineDriverArray
        from globals import OPTS
        array = LevelShiftWordlineDriverArray(rows=16, name="wordline_driver_array",
                                              buffer_stages=OPTS.wordline_buffers)

        self.local_check(array)


LevelShiftWordlineDriverTest.run_tests(__name__)
