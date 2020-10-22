from base import utils
from base.vector import vector
from globals import OPTS
from modules.bitcell_array import bitcell_array


class sotfet_mram_bitcell_array(bitcell_array):

    def add_pins(self):
        for col in range(self.column_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("rwl[{0}]".format(row))
            self.add_pin("wwl[{0}]".format(row))
        self.add_pin("gnd")

    def create_layout(self):

        # make cell name uniform to enable easy swapping out of bitcells

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.column_size)
        self.width = self.bitcell_offsets[-1] + self.cell.width
        self.add_right_dummy = True
        self.add_left_dummy = True

        self.cell_inst = {}
        for row in range(self.row_size):
            if row % 2 == 0:
                y_offset = (row + 1) * self.cell.height
                dir_key = "MX"
            else:
                y_offset = row * self.cell.height
                dir_key = ""
            for col in range(self.column_size):
                name = "bit_r{0}_c{1}".format(row, col)
                inst = self.add_inst(name=name, mod=self.cell,
                                     offset=vector(self.bitcell_offsets[col],
                                                   y_offset), mirror=dir_key)
                self.cell_inst[row, col] = inst
                self.connect_inst(["bl[{0}]".format(col), "br[{0}]".format(col),
                                   "rwl[{0}]".format(row), "wwl[{0}]".format(row), "gnd"])

            for x_offset in self.tap_offsets + OPTS.right_buffers_offsets:
                tap_inst = self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                         offset=vector(x_offset, y_offset), mirror=dir_key)
                self.body_tap_insts.append(tap_inst)
                self.connect_inst([])

        self.fill_right_buffers_implant()

    def add_dummies(self):
        for row in range(self.row_size):
            row_instances = [self.cell_inst[row, x] for x in range(self.column_size)]
            self.add_dummy_poly(self.cell, row_instances, 1)

    def add_layout_pins(self):
        def get_cell_pin(row_, col_, pin_name_="BL"):
            return self.cell_inst[row_, col_].get_pin(pin_name_)

        pin_height = (get_cell_pin(self.row_size - 1, 0).uy() -
                      get_cell_pin(0, 0).by())
        for col in range(self.column_size):
            # get the pin of the lower row cell and make it the full height
            bl_pin = get_cell_pin(0, col)
            br_pin = get_cell_pin(0, col, "BR")
            self.add_layout_pin(text="bl[{0}]".format(col),
                                layer="metal2",
                                offset=bl_pin.ll(),
                                width=bl_pin.width(),
                                height=pin_height)
            self.add_layout_pin(text="br[{0}]".format(col),
                                layer="metal2",
                                offset=br_pin.ll(),
                                width=br_pin.width(),
                                height=pin_height)

        pin_width = (get_cell_pin(0, self.column_size - 1, "RWL").rx() -
                     get_cell_pin(0, 0, "RWL").lx())
        for row in range(self.row_size):
            for pin_name in ["RWL", "WWL"]:
                pin = get_cell_pin(row, 0, pin_name)
                self.add_layout_pin(pin_name.lower() + "[{}]".format(row), pin.layer,
                                    offset=pin.ll(), width=pin_width, height=pin.height())
