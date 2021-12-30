from base.vector import vector
from modules.bitcell_array import bitcell_array


class ReRamBitcellArray(bitcell_array):
    def get_bitcell_connections(self, row, col):
        return f"bl[{col}] br[{col}] wl[{row}] gnd".split()

    def add_layout_pins(self):
        self.add_bitline_layout_pins()
        for row in range(self.row_size):
            wl_pin = self.cell_inst[row][0].get_pin("WL")
            self.add_layout_pin(text="wl[{0}]".format(row),
                                layer=wl_pin.layer,
                                offset=vector(0, wl_pin.by()),
                                width=self.width,
                                height=wl_pin.height())
