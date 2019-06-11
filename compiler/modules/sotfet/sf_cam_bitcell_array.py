import re

from modules import bitcell_array


class sf_cam_bitcell_array(bitcell_array.bitcell_array):
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
        self.add_pin("gnd")

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod.name == "sot_cam_cell":
            all_args = " ".join(args)
            col = re.match(".*bl\[(?P<col>\d+)\]", all_args).group('col')
            row = re.match(".*wl\[(?P<row>\d+)\]", all_args).group('row')

            args = [
                "bl[{0}]".format(col), "br[{0}]".format(col),
                "ml[{0}]".format(row), "wl[{0}]".format(row),
                "gnd"
            ]
        super(sf_cam_bitcell_array, self).connect_inst(args, check)

    def add_layout_pins(self):
        pass
