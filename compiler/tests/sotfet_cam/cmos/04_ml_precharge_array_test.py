#!/usr/bin/env python3
"""
Run a regression test on ml precharge array
"""
from cam_test_base import CamTestBase
import debug


class MlPrechargeArrayTest(CamTestBase):

    def setUp(self):
        super(MlPrechargeArrayTest, self).setUp()
        import tech
        tech.drc_exceptions["sw_matchline_precharge"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tech.drc_exceptions["ml_precharge_array"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]

    def test_min_width_ml_cell(self):
        from modules.sotfet.cmos import sw_matchline_precharge
        debug.info(2, "Checking matchline precharge cell")
        cell = sw_matchline_precharge.sw_matchline_precharge(2)
        self.local_check(cell)

    def test_multiple_fingers_cell(self):
        from modules.sotfet.cmos import sw_matchline_precharge
        from tech import parameter
        from globals import OPTS
        c = __import__(OPTS.bitcell)
        mod_bitcell = getattr(c, OPTS.bitcell)
        bitcell = mod_bitcell()
        debug.info(2, "Checking matchline precharge cell")
        cell = sw_matchline_precharge.sw_matchline_precharge(size=(1.2*bitcell.height)/parameter["min_tx_size"])
        self.local_check(cell)

    def test_precharge_array(self):
        """Test standalone array for drc issues"""
        from modules.sotfet import sf_ml_precharge_array
        rows = 16
        debug.info(2, "Checking matchline precharge array with {} rows")
        array = sf_ml_precharge_array.sf_ml_precharge_array(rows=rows, size=3)
        self.local_check(array)


CamTestBase.run_tests(__name__)
