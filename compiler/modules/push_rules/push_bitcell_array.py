from base.design import design
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.bitcell_array import bitcell_array


@library_import
class bitcell_tap(design):
    lib_name = OPTS.body_tap_mod
    pin_names = ["vdd", "gnd"]


class push_bitcell_array(bitcell_array):
    rotation_for_drc = GDS_ROT_90

    def add_layout_pins(self):

        self.add_bitline_layout_pins()
        if self.dummy_rows:
            row_cells = self.horizontal_dummy[0]
        else:
            row_cells = self.cell_inst[0]
        pin = row_cells[0].get_pin("vdd")
        for i in range(len(row_cells)):
            self.add_layout_pin("vdd", pin.layer,
                                offset=pin.ll(), width=pin.width(),
                                height=self.height - pin.by())

        if self.dummy_cols:
            column_cells = self.vertical_dummy[0]
        else:
            column_cells = [self.cell_inst[row][0]
                            for row in range(self.row_size)]
        for i in range(len(column_cells)):
            cell = column_cells[i]
            for pin_name in ["gnd", "wl"]:
                if pin_name == "gnd":
                    new_pin_name = pin_name
                else:
                    if i in [0, self.row_size + 1]:
                        continue
                    new_pin_name = "wl[{}]".format(i - 1)
                for pin in cell.get_pins(pin_name):
                    self.add_layout_pin(new_pin_name, pin.layer,
                                        offset=pin.ll(),
                                        width=self.width - pin.lx(),
                                        height=pin.height())
        # tap inst vdd
        for pin_name in ["vdd", "gnd"]:
            for pin in self.body_tap_insts[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(),
                                    height=pin.height(), width=self.width - pin.lx())

    def connect_dummy_cell_layouts(self):
        """Connect dummy wordlines to gnd and dummy bitlines to vdd"""
        # wl to gnd
        dummy_insts = [self.vertical_dummy[0][row] for row in self.dummy_rows]
        for dummy_inst in dummy_insts:
            top_gnd = max(dummy_inst.get_pins("gnd"), key=lambda x: x.uy())
            wl = dummy_inst.get_pin("wl")
            x_offset = dummy_inst.cx() - 0.5 * top_gnd.height()
            self.add_rect(top_gnd.layer, offset=vector(x_offset, wl.cy()),
                          width=top_gnd.height(), height=top_gnd.cy() - wl.cy())

        # bl to vdd
        dummy_insts = [self.horizontal_dummy[0][col] for col in self.dummy_cols]
        for dummy_inst in dummy_insts:
            vdd_pin = dummy_inst.get_pin("vdd")
            for pin_name in ["bl", "br"]:
                pin = dummy_inst.get_pin(pin_name)

                self.add_rect(pin.layer, offset=vector(pin.cx(), 0),
                              width=vdd_pin.cx() - pin.cx(), height=vdd_pin.width())

    def add_dummy_polys(self):
        pass
