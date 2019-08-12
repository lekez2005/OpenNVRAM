import re

from modules import bitcell_array


class cam_bitcell_12t_array(bitcell_array.bitcell_array):
    """
    Creates a rows x cols array of memory cells. Assumes bit-lines
    and word line is connected by abutment.
    Has separate read and write wordlines
    Connects the word lines and bit lines.
    """

    def add_pins(self):
        for col in range(self.column_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
            self.add_pin("sl[{0}]".format(col))
            self.add_pin("slb[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("wl[{0}]".format(row))
            self.add_pin("wwl[{0}]".format(row))
            self.add_pin("ml[{0}]".format(row))
        self.add_pin("vdd")
        self.add_pin("gnd")

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod.name == "cam_cell_12t":
            all_args = " ".join(args)
            col = re.match(".*bl\[(?P<col>\d+)\]", all_args).group('col')
            row = re.match(".*wl\[(?P<row>\d+)\]", all_args).group('row')

            args = [
                "bl[{0}]".format(col), "br[{0}]".format(col),
                "sl[{0}]".format(col), "slb[{0}]".format(col),
                "wl[{0}]".format(row), "wwl[{0}]".format(row), "ml[{0}]".format(row),
                "vdd", "gnd"
            ]
        super(cam_bitcell_12t_array, self).connect_inst(args, check)


    def add_layout_pins(self):
        super(cam_bitcell_12t_array, self).add_layout_pins()
        cell_pin_names = ["SL", "SLB"]
        pin_names = ["sl[{0}]", "slb[{0}]"]
        for col in range(self.column_size):
            # get the pin of the lower row cell and make it the full width

            for pin_index in range(2):
                cell_pin_name = cell_pin_names[pin_index]
                bot_pin = self.cell_inst[0, col].get_pin(cell_pin_name)
                top_pin = self.cell_inst[self.row_size-1, col].get_pin(cell_pin_name)
                self.add_layout_pin(text=pin_names[pin_index].format(col),
                                    layer=bot_pin.layer,
                                    offset=bot_pin.ll(),
                                    width=bot_pin.width(),
                                    height=top_pin.uy() - bot_pin.by())

        for row in range(self.row_size):
            for (cell_pin_name, module_pin_name) in [("ML", "ml[{0}]"), ("WWL", "wwl[{0}]")]:
                # add ml_pin
                leftmost_pin = self.cell_inst[row, 0].get_pin(cell_pin_name)
                rightmost_pin = self.cell_inst[row, self.column_size-1].get_pin(cell_pin_name)
                # add ml pin label and offset
                self.add_layout_pin(text=module_pin_name.format(row),
                                    layer=leftmost_pin.layer,
                                    offset=leftmost_pin.ll(),
                                    width=rightmost_pin.rx()-leftmost_pin.lx(),
                                    height=leftmost_pin.height())
