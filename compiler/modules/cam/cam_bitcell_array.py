import re

from base.vector import vector
from modules import bitcell_array


class cam_bitcell_array(bitcell_array.bitcell_array):
    """
    Creates a rows x cols array of memory cells. Assumes bit-lines
    and word line is connected by abutment.
    Connects the word lines and bit lines.
    """

    def add_pins(self):
        for col in range(self.column_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("wl[{0}]".format(row))
            self.add_pin("ml[{0}]".format(row))
        self.add_pin("vdd")
        self.add_pin("gnd")

    def get_conns_row_col(self, connections):
        all_args = " ".join(connections)
        col = re.match(".*bl\[(?P<col>\d+)\]", all_args).group('col')
        row = re.match(".*wl\[(?P<row>\d+)\]", all_args).group('row')
        return row, col

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod.name == self.cell.name:
            row, col = self.get_conns_row_col(args)
            args = [
                "bl[{0}]".format(col), "br[{0}]".format(col),
                "wl[{0}]".format(row), "ml[{0}]".format(row),
                "vdd", "gnd"
            ]
        super(cam_bitcell_array, self).connect_inst(args, check)

    def add_layout_pins(self):
        self.child_mod = self.cell
        super(cam_bitcell_array, self).add_layout_pins()

        for row in range(self.row_size):
            # add ml_pin
            left_ml_pin = self.cell_inst[row][0].get_pin("ML")
            right_ml_pin = self.cell_inst[row][self.column_size - 1].get_pin("ML")
            # add ml pin label and offset
            self.add_layout_pin(text="ml[{0}]".format(row),
                                layer=right_ml_pin.layer,
                                offset=vector(left_ml_pin.lx(), right_ml_pin.by()),
                                width=right_ml_pin.rx() - left_ml_pin.lx(),
                                height=right_ml_pin.height())
