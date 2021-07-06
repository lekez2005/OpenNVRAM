#!/usr/bin/env python3
"""
Run a regression test on ml precharge array
"""
from cam_test_base import CamTestBase
import debug


class MlPrechargeArrayTest(CamTestBase):

    def test_min_width_ml_cell(self):
        from modules.sotfet import sf_matchline_precharge
        debug.info(2, "Checking matchline precharge cell")
        cell = sf_matchline_precharge.sf_matchline_precharge(2)
        self.local_check(cell)

    def test_multiple_fingers_cell(self):
        from modules.sotfet.sf_matchline_precharge import sf_matchline_precharge
        from tech import parameter

        bitcell = self.load_class_from_opts("bitcell")()
        debug.info(2, "Checking matchline precharge cell")
        cell = sf_matchline_precharge(size=(1.2*bitcell.height)/parameter["min_tx_size"])
        self.local_check(cell)

    def test_precharge_array(self):
        """Test standalone array for drc issues"""
        from modules.sotfet import sf_ml_precharge_array
        rows = 16
        debug.info(2, "Checking matchline precharge array with {} rows")
        array = sf_ml_precharge_array.sf_ml_precharge_array(rows=rows, size=3)
        self.local_check(array)


CamTestBase.run_tests(__name__)
