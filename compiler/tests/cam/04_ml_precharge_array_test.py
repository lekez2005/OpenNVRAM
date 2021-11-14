#!/usr/bin/env python3
"""
Run a regression test on ml precharge array
"""

from cam_test_base import CamTestBase


# class MlPrechargeArrayTest(CamTestBase):
#
#     def test_min_width_ml_cell(self):
#         self.debug.info(2, "Checking matchline precharge cell")
#         cell = self.create_class_from_opts("ml_precharge", size=1)
#         self.local_check(cell)
#
#     def test_multiple_fingers_cell(self):
#         from tech import parameter
#         bitcell = self.create_class_from_opts("bitcell")
#         size = (1.2 * bitcell.height) / parameter["min_tx_size"]
#         self.debug.info(2, f"Checking matchline precharge cell with size {size:.2g}")
#         cell = self.create_class_from_opts("ml_precharge", size=size)
#         self.local_check(cell)
#
#     def test_precharge_array(self):
#         """Test standalone array for drc issues"""
#         rows = 16
#         self.debug.info(2, "Checking matchline precharge array with {} rows")
#         array = self.create_class_from_opts("ml_precharge_array", rows=rows, size=3)
#         self.local_check(array)


class CamPrechargeTest(CamTestBase):

    def test_multiple_fingers_cell(self):
        size = 4
        self.debug.info(2, f"Checking matchline precharge cell with size {size:.2g}")
        cell = self.create_class_from_opts("precharge", name="precharge", size=size)
        self.local_check(cell)

    # def test_no_precharge(self):
    #     size = 4
    #     self.debug.info(2, f"Checking matchline precharge cell with size {size:.2g}")
    #     cell = self.create_class_from_opts("precharge", name="precharge", size=size,
    #                                        has_precharge=False)
    #     self.local_check(cell)
    #
    # def test_with_precharge(self):
    #     size = 4
    #     self.debug.info(2, f"Checking matchline precharge cell with size {size:.2g}")
    #     cell = self.create_class_from_opts("precharge", name="precharge", size=size,
    #                                        has_precharge=True)
    #     self.local_check(cell)
    #
    # def test_precharge_array(self):
    #     """Test standalone array for drc issues"""
    #     cols = 16
    #     self.debug.info(2, "Checking matchline precharge array with {} rows")
    #     array = self.create_class_from_opts("precharge_array", columns=cols, size=3,
    #                                         has_precharge=False)
    #     self.local_check(array)
    #
    #     array = self.create_class_from_opts("precharge_array", columns=cols, size=3,
    #                                         has_precharge=True)
    #     self.local_check(array)


CamTestBase.run_tests(__name__)
