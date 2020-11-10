import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(parent_dir))

import testutils


class TestBase(testutils.OpenRamTest):
    config_template = "config_push_hs_{}"

    def add_body_tap_and_test(self, dut_):
        from base.design import design
        from base.hierarchy_layout import GDS_ROT_90
        from base.vector import vector
        from modules.push_rules.pgate_horizontal import pgate_horizontal
        from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap

        class WrappedDut(design):
            rotation_for_drc = GDS_ROT_90

            def __init__(self, dut: pgate_horizontal):
                name = dut.name + "_and_tap"
                design.__init__(self, name)
                self.dut = dut
                self.add_mod(dut)

                tap = pgate_horizontal_tap(dut)
                self.add_mod(tap)

                dut_inst = self.add_inst("dut", mod=self.dut, offset=vector(0, 0))
                self.connect_inst(self.dut.pins)

                tap_inst = self.add_inst("tap", mod=tap, offset=dut_inst.lr())
                self.connect_inst([])

                for pin_name in self.dut.pins:
                    self.add_pin(pin_name)
                    self.copy_layout_pin(dut_inst, pin_name, pin_name)

                self.width = tap_inst.rx()
                self.height = dut.height

        real_dut = WrappedDut(dut_)
        super().local_check(real_dut)
