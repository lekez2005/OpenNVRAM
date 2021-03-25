import math
from typing import List, Dict

import debug
from base.design import design
from base.geometry import instance
from base.hierarchy_layout import GDS_ROT_90
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.bitcell_array import bitcell_array
from tech import drc, add_tech_layers


@library_import
class bitcell_tap(design):
    lib_name = OPTS.body_tap_mod
    pin_names = ["vdd", "gnd"]


class push_bitcell_array(bitcell_array):
    rotation_for_drc = GDS_ROT_90

    def __init__(self, cols, rows, name="bitcell_array"):
        design.__init__(self, name)
        debug.info(1, "Creating {0} {1} x {2}".format(self.name, rows, cols))

        self.cell = self.create_mod_from_str(OPTS.bitcell)
        self.bitcell = self.cell
        self.body_tap = self.create_mod_from_str(OPTS.body_tap)

        self.column_size = cols
        self.row_size = rows

        self.add_pins()

        self.cell_inst = [[None] * cols for x in range(rows)]  # type: List[List[instance]]
        self.dummy_inst = {
            "vertical": [[None] * (rows + 2) for x in range(2)],
            "horizontal": [[None] * (cols + 2) for x in range(2)]
        }  # type: Dict[str, List[List[instance]]]

        self.horizontal_dummy = self.dummy_inst["horizontal"]
        self.vertical_dummy = self.dummy_inst["vertical"]

        self.tap_inst = []

        self.create_layout()
        self.add_dummy_instances()
        self.calculate_repeater_offsets()

        add_tech_layers(self)

        self.add_layout_pins()
        self.connect_dummies()

    @staticmethod
    def get_bitcell_offsets(num_rows: int, cells_per_group: int, bitcell, body_tap):
        num_rows += 2  # for dummies
        bitcell_height = bitcell.height
        tap_height = body_tap.height

        cell_spacing = int(math.floor(0.95 * drc["latchup_spacing"] / bitcell.height)
                           - cells_per_group)
        tap_indices = list(range(cell_spacing, num_rows, cell_spacing))
        if len(tap_indices) == 0:
            tap_indices = [int(num_rows / 2)]
        elif tap_indices[-1] == num_rows - 1:  # avoid putting at top of array to make it predictable
            tap_indices[-1] = [num_rows - 4]
        # normalize by cells_per_group
        tap_indices = [x - (x % cells_per_group) for x in tap_indices]
        # offset by 1 since first cell will be mirrored
        tap_indices = [x + 1 for x in tap_indices]

        bitcell_offsets = []
        tap_offsets = []
        y_offset = 0
        for i in range(num_rows):
            if i in tap_indices:
                tap_offsets.append(y_offset)
                y_offset += tap_height
            bitcell_offsets.append(y_offset)
            y_offset += bitcell_height

        dummy_offsets = [bitcell_offsets[0], bitcell_offsets[-1]]

        return bitcell_offsets[1:-1], tap_offsets, dummy_offsets

    def get_cell_offset(self, col_index, row_index):
        x_offset = col_index * self.bitcell.width
        if row_index % 2 == 1:
            y_offset = self.all_y_offsets[row_index]
            if col_index % 2 == 0:
                mirror = ""
            else:
                mirror = "MY"
                x_offset += self.bitcell.width
        else:
            y_offset = self.all_y_offsets[row_index] + self.bitcell.height
            if col_index % 2 == 0:
                mirror = "MX"
            else:
                mirror = "XY"
                x_offset += self.bitcell.width
        return x_offset, y_offset, mirror

    def calculate_repeater_offsets(self):
        add_repeaters = (OPTS.add_buffer_repeaters and
                         self.column_size > OPTS.buffer_repeaters_col_threshold and
                         len(OPTS.buffer_repeater_sizes) > 0)
        if not add_repeaters:
            return
        OPTS.dedicated_repeater_space = False
        OPTS.buffer_repeaters_x_offset = OPTS.repeater_x_offset * self.width

    def create_layout(self):
        self.bitcell_offsets = [(i + 1) * self.bitcell.width for i in range(self.column_size)]

        self.bitcell_y_offsets, self.tap_offsets, self.dummy_offsets = \
            self.get_bitcell_offsets(self.row_size, 2, self.bitcell, self.body_tap)
        self.all_y_offsets = ([self.dummy_offsets[0]] + self.bitcell_y_offsets
                              + [self.dummy_offsets[-1]])
        for col in range(self.column_size):
            for row in range(self.row_size):
                name = "bit_r{0}_c{1}".format(row, col)

                x_offset, y_offset, mirror = self.get_cell_offset(col + 1, row + 1)

                cell_inst = self.add_inst(name=name, mod=self.bitcell,
                                          offset=vector(x_offset, y_offset),
                                          mirror=mirror)
                self.cell_inst[row][col] = cell_inst
                self.connect_inst(["bl[{0}]".format(col), "br[{0}]".format(col),
                                   "wl[{0}]".format(row), "vdd", "gnd"])

        for col in range(self.column_size + 2):
            if col % 2 == 0:
                x_offset = col * self.bitcell.width
                mirror = ""
            else:
                x_offset = (1 + col) * self.bitcell.width
                mirror = "MY"

            for y_offset in self.tap_offsets:
                tap_inst = self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                         offset=vector(x_offset, y_offset), mirror=mirror)
                self.connect_inst([])
                self.tap_inst.append(tap_inst)

    def add_dummy_instances(self):
        """Add dummy on all four edges. Total rows = rows + 2, total_cols = cols + 2"""

        cols = [0, self.column_size + 1]

        # vertical
        for i in range(2):
            col = cols[i]
            for row in range(self.row_size + 2):
                name = "dummy_r{0}_c{1}".format(row, col)
                x_offset, y_offset, mirror = self.get_cell_offset(col, row)
                dummy_inst = self.add_inst(name=name, mod=self.bitcell,
                                           offset=vector(x_offset, y_offset),
                                           mirror=mirror)
                if row in [0, self.row_size + 1]:
                    wl_conn = "gnd"
                else:
                    wl_conn = "wl[{0}]".format(row - 1)
                self.connect_inst("vdd vdd {1} vdd gnd".
                                  format(col, wl_conn).split())
                self.dummy_inst["vertical"][i][row] = dummy_inst

        # horizontal
        self.horizontal_dummy[0][0] = self.vertical_dummy[0][0]
        self.horizontal_dummy[0][-1] = self.vertical_dummy[1][0]
        self.horizontal_dummy[1][0] = self.vertical_dummy[0][-1]
        self.horizontal_dummy[1][-1] = self.vertical_dummy[1][-1]
        rows = [0, self.row_size + 1]
        for i in range(2):
            for col in range(self.column_size):
                x_offset, y_offset, mirror = self.get_cell_offset(col + 1, rows[i])
                name = "dummy_r{0}_c{1}".format(rows[i], col + 1)
                dummy_inst = self.add_inst(name=name, mod=self.bitcell,
                                           offset=vector(x_offset, y_offset),
                                           mirror=mirror)
                self.connect_inst("bl[{0}] br[{0}] gnd vdd gnd".
                                  format(col, rows[i]).split())
                self.horizontal_dummy[i][col + 1] = dummy_inst

        self.width = self.horizontal_dummy[-1][-1].rx()
        self.height = self.vertical_dummy[-1][-1].uy()

    def add_layout_pins(self):
        column_cells = self.vertical_dummy[0]
        row_cells = self.horizontal_dummy[0]
        for i in range(len(row_cells)):
            cell = row_cells[i]
            for pin_name in ["bl", "br", "vdd"]:
                if pin_name == "vdd":
                    new_pin_name = pin_name
                else:
                    if i in [0, self.column_size + 1]:
                        continue
                    if i % 2 == 1:
                        if pin_name == "bl":
                            prefix = "br"
                        else:
                            prefix = "bl"
                    else:
                        prefix = pin_name
                    new_pin_name = prefix + "[{}]".format(i - 1)

                pin = cell.get_pin(pin_name)
                self.add_layout_pin(new_pin_name, pin.layer,
                                    offset=pin.ll(), width=pin.width(),
                                    height=self.height - pin.by())
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
                                        offset=pin.ll(), width=self.width - pin.lx(),
                                        height=pin.height())
        # tap inst vdd
        for pin_name in ["vdd", "gnd"]:
            for pin in self.tap_inst[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(),
                                    height=pin.height(), width=self.width - pin.lx())

    def connect_dummies(self):
        """Connect dummy wordlines to gnd and dummy bitlines to vdd"""
        # wl to gnd
        for dummy_inst in [self.vertical_dummy[0][0],
                           self.vertical_dummy[0][-1]]:
            top_gnd = max(dummy_inst.get_pins("gnd"), key=lambda x: x.uy())
            wl = dummy_inst.get_pin("wl")
            x_offset = dummy_inst.cx() - 0.5 * top_gnd.height()
            self.add_rect(top_gnd.layer, offset=vector(x_offset, wl.cy()),
                          width=top_gnd.height(), height=top_gnd.cy() - wl.cy())

        # bl to vdd
        for dummy_inst in [self.vertical_dummy[0][0],
                           self.vertical_dummy[1][0]]:
            vdd_pin = dummy_inst.get_pin("vdd")
            for pin_name in ["bl", "br"]:
                pin = dummy_inst.get_pin(pin_name)

                self.add_rect(pin.layer, offset=vector(pin.cx(), 0),
                              width=vdd_pin.cx() - pin.cx(), height=vdd_pin.width())
