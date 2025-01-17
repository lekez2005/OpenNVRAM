from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.precharge_array import precharge_array
from modules.push_rules.precharge_horizontal import precharge_horizontal


class PrechargeArray(precharge_array):
    rotation_for_drc = GDS_ROT_270

    def create_modules(self):
        self.pc_cell = precharge_horizontal(name="precharge", size=self.size)
        self.child_mod = self.pc_cell
        self.add_mod(self.pc_cell)

    def add_insts(self):
        self.child_insts = []
        x_base = self.pc_cell.width
        for i in range(self.columns):
            x_offset = x_base + i * self.pc_cell.width
            if i % 2 == 1:
                x_offset += self.pc_cell.width
                mirror = "MY"
                bl_pin, br_pin = "br", "bl"
            else:
                mirror = ""
                bl_pin, br_pin = "bl", "br"
            name = "mod_{0}".format(i)
            inst = self.add_inst(name=name, mod=self.pc_cell, offset=vector(x_offset, 0),
                                 mirror=mirror)
            self.connect_inst(["bl[{0}]".format(i), "br[{0}]".format(i),
                               "en", "vdd"])
            self.copy_layout_pin(inst, bl_pin, "bl[{0}]".format(i))
            self.copy_layout_pin(inst, br_pin, "br[{0}]".format(i))
            self.child_insts.append(inst)
        self.width = (2 + self.columns) * self.pc_cell.width
        self.height = self.pc_cell.height
        self.add_boundary()
