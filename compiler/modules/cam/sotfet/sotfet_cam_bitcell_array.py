from modules.cam.cam_bitcell_array import cam_bitcell_array


class SotfetCamBitcellArray(cam_bitcell_array):
    def add_pin(self, name, pin_type=None):
        if name == "vdd":
            return
        super().add_pin(name, pin_type)

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod.name == self.cell.name:
            row, col = self.get_conns_row_col(args)
            args = [
                "bl[{0}]".format(col), "br[{0}]".format(col),
                "ml[{0}]".format(row), "wl[{0}]".format(row),
                "gnd"
            ]
        super(cam_bitcell_array, self).connect_inst(args, check)
