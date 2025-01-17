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

    def get_bitcell_connections(self, row, col):
        connections = super().get_bitcell_connections(row, col)
        connections[3] = connections[2].replace("wl", "wwl")
        connections[2] = connections[2].replace("wl", "rwl")
        return connections

    def add_layout_pins(self):
        def get_cell_pin(row_, col_, pin_name_="BL"):
            return self.get_cell_inst_row(row_ + OPTS.num_bitcell_dummies)[col_].get_pin(pin_name_)

        self.add_bitline_layout_pins()

        pin_width = (get_cell_pin(0, self.column_size - 1 + 2 * OPTS.num_bitcell_dummies, "RWL").rx() -
                     get_cell_pin(0, 0, "RWL").lx())
        for row in range(self.row_size):
            for pin_name in ["RWL", "WWL"]:
                pin = get_cell_pin(row, 0, pin_name)
                self.add_layout_pin(pin_name.lower() + "[{}]".format(row), pin.layer,
                                    offset=pin.ll(), width=pin_width, height=pin.height())

        self.add_body_tap_power_pins()

    def add_body_tap_power_pins(self):
        # tap inst vdd
        for pin in self.body_tap.get_pins("gnd"):
            if pin.width() > pin.height():
                for y_offset in self.bitcell_y_offsets[1]:
                    self.add_layout_pin("gnd", pin.layer,
                                        offset=vector(pin.lx(), pin.by() + y_offset),
                                        height=pin.height(), width=self.width - pin.lx())
                else:
                    for x_offset in self.bitcell_x_offsets[1]:
                        self.add_layout_pin("gnd", pin.layer,
                                            offset=vector(x_offset + pin.lx(), pin.by()),
                                            height=self.height - pin.by(),
                                            width=pin.width())
