from base import utils
from base.vector import vector
from modules import bitcell_array


class sf_cam_bitcell_array(bitcell_array.bitcell_array):
    """
    Creates a rows x cols array of memory cells. Assumes bit-lines
    and word line is connected by abutment.
    Connects the word lines and bit lines.
    """
    bitcell_offsets = []
    cell_inst = {}

    def add_pins(self):
        for col in range(self.column_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("wl[{0}]".format(row))
            self.add_pin("ml[{0}]".format(row))
        self.add_pin("gnd")

    def create_layout(self):
        (self.bitcell_offsets, tap_offsets) = utils.get_tap_positions(self.column_size)
        yoffset = 0.0
        for row in range(self.row_size):
            if row % 2 == 1:
                tempy = yoffset + self.cell.height
                dir_key = "MX"
            else:
                tempy = yoffset
                dir_key = ""
            for col in range(self.column_size):
                name = "bit_r{0}_c{1}".format(row, col)

                self.cell_inst[row, col]=self.add_inst(name=name, mod=self.cell,
                                                       offset=[self.bitcell_offsets[col], tempy],
                                                       mirror=dir_key)
                connections = [
                    "bl[{0}]".format(col), "br[{0}]".format(col),
                    "ml[{0}]".format(row), "wl[{0}]".format(row),
                    "mz1_c{}_r{}".format(col, row),
                    "gnd"
                ]
                self.connect_inst(connections)

            for x_offset in tap_offsets:
                self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                         offset=vector(x_offset, tempy), mirror=dir_key))
                self.connect_inst([])

            yoffset += self.cell.height

        self.width = self.get_full_width()

    def get_full_width(self):
        return max(max(self.cell_inst.values(), key=lambda x: x.rx()).rx(),
                   max(self.body_tap_insts, key=lambda x: x.rx()).rx())

    def get_full_height(self):
        return self.height, 0

    def add_dummies(self):
        self.add_left_dummy = False
        self.add_right_dummy = True
        super().add_dummies()

    def add_layout_pins(self):
        super().add_layout_pins()
        for row in range(self.row_size):
            # add wl label and offset
            ml_pin = self.cell_inst[row, 0].get_pin("ML")
            self.add_layout_pin(text="ml[{0}]".format(row),
                                layer=ml_pin.layer,
                                offset=vector(0, ml_pin.by()),
                                width=self.get_full_width(),
                                height=ml_pin.height())
