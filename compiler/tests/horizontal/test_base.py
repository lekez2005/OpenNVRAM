import os
import sys

parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
parent_dir = os.path.abspath(parent_dir)
shared_dir = os.path.join(parent_dir, "shared_decoder")
sys.path.insert(1, parent_dir)
sys.path.insert(1, shared_dir)

from shared_decoder.test_base import TestBase as SharedTestBase


class TestBase(SharedTestBase):

    def add_body_tap_and_test(self, dut_):
        from base.design import design, PIMP, NIMP
        from base.hierarchy_layout import GDS_ROT_90
        from base.vector import vector
        from modules.buffer_stage import BufferStage
        from modules.horizontal.pgate_horizontal import pgate_horizontal
        from modules.horizontal.wordline_pgate_horizontal import wordline_pgate_horizontal

        class WrappedDut(design):
            rotation_for_drc = GDS_ROT_90

            def __init__(self, dut: pgate_horizontal):
                name = dut.name + "_and_tap"
                design.__init__(self, name)
                self.dut = dut
                self.add_mod(dut)

                dut_inst = self.add_inst("dut", mod=self.dut, offset=vector(0, 0))
                self.connect_inst(self.dut.pins)

                if isinstance(dut, (wordline_pgate_horizontal, BufferStage)):
                    from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap

                    if isinstance(dut, BufferStage):
                        pwell_tap = wordline_pgate_tap(dut.buffer_invs[0], PIMP)
                        nwell_tap = wordline_pgate_tap(dut.buffer_invs[0], NIMP)
                        inst_list = dut.module_insts
                    else:
                        pwell_tap = wordline_pgate_tap(dut, PIMP)
                        nwell_tap = wordline_pgate_tap(dut, NIMP)
                        inst_list = [dut_inst]
                    wordline_pgate_tap.add_buffer_taps(self, 0, dut_inst.uy(),
                                                       inst_list,
                                                       pwell_tap, nwell_tap)
                    self.width = dut.width
                else:
                    from modules.horizontal.pgate_horizontal_tap import pgate_horizontal_tap
                    tap = pgate_horizontal_tap(dut)
                    self.add_mod(tap)

                    tap_inst = self.add_inst("tap", mod=tap, offset=dut_inst.lr())
                    self.connect_inst([])
                    self.width = tap_inst.rx()

                for pin_name in self.dut.pins:
                    self.add_pin(pin_name)
                    self.copy_layout_pin(dut_inst, pin_name, pin_name)

                self.height = dut.height

        real_dut = WrappedDut(dut_)
        super().local_check(real_dut)
