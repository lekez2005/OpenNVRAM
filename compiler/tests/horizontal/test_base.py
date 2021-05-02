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
        from modules.logic_buffer import LogicBuffer
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

                if isinstance(dut, (wordline_pgate_horizontal, BufferStage, LogicBuffer)):
                    from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap

                    if isinstance(dut, BufferStage):
                        pwell_tap = wordline_pgate_tap(dut.buffer_invs[0], PIMP)
                        nwell_tap = wordline_pgate_tap(dut.buffer_invs[0], NIMP)
                        inst_lists = [dut.module_insts]
                        x_offsets = [0]
                        add_taps = [True]
                    elif isinstance(dut, LogicBuffer):
                        pwell_tap = wordline_pgate_tap(dut.logic_mod, PIMP)
                        nwell_tap = wordline_pgate_tap(dut.logic_mod, NIMP)
                        inst_lists = [[dut.logic_inst],
                                      dut.buffer_mod.module_insts[:1],
                                      dut.buffer_mod.module_insts[1:]]
                        x_offsets = [0, dut.buffer_inst.lx(), dut.buffer_inst.lx()]
                        add_taps = [True, False, True]
                    else:
                        pwell_tap = wordline_pgate_tap(dut, PIMP)
                        nwell_tap = wordline_pgate_tap(dut, NIMP)
                        inst_lists = [[dut_inst]]
                        x_offsets = [0]
                        add_taps = [True]
                    for x_offset, inst_list, add_tap in zip(x_offsets, inst_lists, add_taps):
                        wordline_pgate_tap.add_buffer_taps(self, x_offset, dut_inst.uy(),
                                                           inst_list,
                                                           pwell_tap, nwell_tap, add_taps=add_tap)
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
