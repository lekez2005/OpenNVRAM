#!/usr/bin/env python3

from cam_test_base import CamTestBase
import debug


class CamControlLogicTest(CamTestBase):

    def test_control_logic_buffer(self):
        from modules import control_logic_buffer
        debug.info(2, "Test control logic buffer")

        cell = control_logic_buffer.ControlLogicBuffer([3, 8])
        self.local_check(cell)

    def test_no_column_mux(self):
        from modules.cam import cam_control_logic
        debug.info(1, "No column mux")
        a = cam_control_logic.cam_control_logic(num_rows=128)
        self.local_check(a)


CamTestBase.run_tests(__name__)
