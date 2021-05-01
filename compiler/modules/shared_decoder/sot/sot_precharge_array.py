from globals import OPTS
from modules.horizontal.precharge_reset_array import PrechargeResetArray


class SotPrechargeArray(PrechargeResetArray):

    def add_pins(self):
        super().add_pins()
        for i in range(OPTS.num_reference_cells):
            self.add_pin_list("ref_bl[{0}] ref_br[{0}]".format(i).split())

    def add_insts(self):
        super().add_insts()
        for i in range(OPTS.num_reference_cells):
            name = "pre_ref_{0}".format(i)
            x_offset = OPTS.reference_cell_x + i * self.pc_cell.width
            if (i + OPTS.num_dummies) % 2 == 0:
                x_offset += self.pc_cell.width

            mod, offset, mirror = self.get_col_mod(i)
            offset.x = x_offset
            inst = self.add_inst(name=name, mod=mod, offset=offset, mirror=mirror)
            self.connect_inst("ref_bl[{0}] ref_br[{0}]".format(i).split() +
                              ["en", "bl_reset", "br_reset", "vdd", "gnd"])

            self.copy_layout_pin(inst, "bl", "ref_bl[{0}]".format(i))
            self.copy_layout_pin(inst, "br", "ref_br[{0}]".format(i))
