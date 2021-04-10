from base.geometry import MIRROR_Y_AXIS, NO_MIRROR
from base.vector import vector
from globals import OPTS
from modules.horizontal.precharge_and_reset import PrechargeAndReset
from modules.precharge_array import precharge_array


class PrechargeResetArray(precharge_array):

    def create_modules(self):
        self.pc_cell = PrechargeAndReset(name="precharge", size=self.size)
        self.add_mod(self.pc_cell)

        if OPTS.symmetric_bitcell:
            self.pc_cell_mirror = PrechargeAndReset(name="precharge_mirror", size=self.size,
                                                    mirror=True)
            self.add_mod(self.pc_cell_mirror)
        else:
            self.pc_cell_mirror = self.pc_cell

    def add_pins(self):
        super().add_pins()
        self.add_pin("br_reset")
        self.add_pin("gnd")

    def create_layout(self):
        self.add_insts()
        for pin_name in ["vdd", "gnd", "br_reset", "en"]:
            for pin in self.pc_cell.get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, pin.ll(),
                                    width=self.width - pin.lx(),
                                    height=pin.height())

    def get_col_mod(self, col):
        offset = vector(self.bitcell_offsets[col], 0)
        if (col + OPTS.num_dummies) % 2 == 0:
            mirror = MIRROR_Y_AXIS
            offset.x += self.pc_cell.width
            mod = self.pc_cell_mirror
        else:
            mirror = NO_MIRROR
            mod = self.pc_cell
        return mod, offset, mirror

    def add_insts(self):
        """Creates a precharge array by horizontally tiling the precharge cell"""
        bitcell_array_cls = self.import_mod_class_from_str(OPTS.bitcell_array)
        offsets = bitcell_array_cls.calculate_x_offsets(num_cols=self.columns)

        (self.bitcell_offsets, self.tap_offsets, _) = offsets

        self.child_insts = []
        for i in range(self.columns):
            name = "pre_column_{0}".format(i)
            mod, offset, mirror = self.get_col_mod(i)
            inst = self.add_inst(name=name, mod=mod, offset=offset,
                                 mirror=mirror)

            self.copy_layout_pin(inst, "bl", "bl[{0}]".format(i))
            self.copy_layout_pin(inst, "br", "br[{0}]".format(i))
            self.connect_inst(["bl[{0}]".format(i), "br[{0}]".format(i),
                               "en", "br_reset", "vdd", "gnd"])
            self.child_insts.append(inst)
        self.width = inst.rx()
