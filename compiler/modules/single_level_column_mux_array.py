import debug
from base import contact
from base import design
from base import utils
from base.contact import m1m2, cross_m1m2
from base.design import METAL2, PWELL, ACTIVE
from base.vector import vector
from globals import OPTS
from modules.single_level_column_mux import single_level_column_mux
from tech import info


class single_level_column_mux_array(design.design):
    """
    Dynamically generated column mux array.
    Array of column mux to read the bitlines through the 6T.
    """

    def __init__(self, columns, word_size):
        design.design.__init__(self, "columnmux_array")
        debug.info(1, "Creating {0}".format(self.name))
        self.columns = columns
        self.word_size = word_size
        self.words_per_row = int(self.columns / self.word_size)
        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.columns):
            self.add_pin("bl[{}]".format(i))
            self.add_pin("br[{}]".format(i))
        for i in range(self.words_per_row):
            self.add_pin("sel[{}]".format(i))
        for i in range(self.word_size):
            self.add_pin("bl_out[{}]".format(i))
            self.add_pin("br_out[{}]".format(i))
        self.add_pin("gnd")

    def create_layout(self):
        self.add_modules()
        self.setup_layout_constants()
        self.create_array()
        self.add_routing()
        # Find the highest shapes to determine height before adding well
        highest = self.find_highest_coords()
        self.height = highest.y
        self.width = self.child_insts[-1].rx()
        self.add_layout_pins()
        self.add_boundary()

    def add_modules(self):
        self.mux = single_level_column_mux(tx_size=OPTS.column_mux_size)
        self.child_mod = self.mux
        self.add_mod(self.mux)

    def setup_layout_constants(self):
        self.column_addr_size = int(self.words_per_row / 2)
        self.bus_pitch = self.bus_width + self.bus_space
        # one set of metal1 routes for select signals and a pair to interconnect the mux outputs bl/br
        # two extra route pitch is to space from the sense amp
        self.route_height = (self.words_per_row + 4) * self.bus_pitch

    def create_array(self):
        self.child_insts = []

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)

        # For every column, add a pass gate
        for col_num in range(self.columns):
            name = "MUX{0}".format(col_num)
            x_off = vector(self.bitcell_offsets[col_num], self.route_height)
            self.child_insts.append(self.add_inst(name=name, mod=self.mux, offset=x_off))

            self.connect_inst(["bl[{}]".format(col_num),
                               "br[{}]".format(col_num),
                               "bl_out[{}]".format(int(col_num / self.words_per_row)),
                               "br_out[{}]".format(int(col_num / self.words_per_row)),
                               "sel[{}]".format(col_num % self.words_per_row),
                               "gnd"])

    def add_layout_pins(self):
        """ Add the pins after we determine the height. """
        # For every column, add a pass gate
        for col_num in range(self.columns):
            child_insts = self.child_insts[col_num]
            self.copy_layout_pin(child_insts, "bl", "bl[{}]".format(col_num))
            self.copy_layout_pin(child_insts, "br", "br[{}]".format(col_num))

        cell_gnd_pin = self.child_insts[0].get_pin("gnd")
        self.add_layout_pin("gnd", "metal1", offset=cell_gnd_pin.ll(),
                            width=self.width - cell_gnd_pin.lx(),
                            height=cell_gnd_pin.height())

    def add_routing(self):
        self.add_horizontal_input_rail()
        self.add_vertical_gate_rail()
        self.route_bitlines()

    def add_horizontal_input_rail(self):
        """ Create address input rails on M1 below the mux transistors  """
        for j in range(self.words_per_row):
            offset = vector(0, self.route_height - (j + 1) * self.bus_pitch)
            self.add_layout_pin(text="sel[{}]".format(j),
                                layer="metal1",
                                offset=offset,
                                width=self.child_insts[-1].get_pin("sel").rx() + 0.5 * m1m2.height,
                                height=self.bus_width)

    def add_vertical_gate_rail(self):
        """  Connect the selection gate to the address rails """

        # Offset to the first transistor gate in the pass gate
        for col in range(self.columns):
            # which select bit should this column connect to depends on the position in the word
            sel_index = col % self.words_per_row
            # Add the column x offset to find the right select bit

            gate_pin = self.child_insts[col].get_pin("sel")

            sel_pos = vector(gate_pin.lx(), self.get_pin("sel[{}]".format(sel_index)).cy())

            self.add_rect("metal2", offset=sel_pos, height=gate_pin.by() - sel_pos.y)

            self.add_cross_contact_center(cross_m1m2, offset=vector(gate_pin.cx(), sel_pos.y),
                                          rotate=True)

    def get_output_bitlines(self, col):
        return self.child_insts[col].get_pin("bl_out"), self.child_insts[col].get_pin("br_out")

    def route_bitlines(self):
        """  Connect the output bit-lines to form the appropriate width mux """
        bl_out_y = self.get_pin("sel[{}]".format(self.words_per_row - 1)).by() - self.bus_pitch
        br_out_y = bl_out_y - self.bus_pitch

        cross_via_extension = 0.5 * cross_m1m2.height

        for j in range(self.columns):
            bl_out, br_out = self.get_output_bitlines(j)

            bl_out_offset = vector(bl_out.lx() - cross_via_extension, bl_out_y)
            br_out_offset = vector(br_out.lx() - cross_via_extension, br_out_y)

            if (j % self.words_per_row) == 0:
                # Create the metal1 to connect the n-way mux output from the pass gate
                # These will be located below the select lines. Yes, these are M2 width
                # to ensure vias are enclosed and M1 min width rules.

                width = (contact.m1m2.width + self.bitcell_offsets[j + self.words_per_row - 1]
                         - self.bitcell_offsets[j] + 2 * cross_via_extension)
                self.add_rect(layer="metal1",
                              offset=bl_out_offset,
                              width=width,
                              height=self.bus_width)
                self.add_rect(layer="metal1",
                              offset=br_out_offset,
                              width=width,
                              height=self.bus_width)

                # Extend the bitline output rails and gnd downward on the first bit of each n-way mux
                self.add_layout_pin(text="bl_out[{}]".format(int(j / self.words_per_row)),
                                    layer="metal2",
                                    offset=vector(bl_out.lx(), 0),
                                    width=bl_out.width(),
                                    height=self.route_height)
                self.add_layout_pin(text="br_out[{}]".format(int(j / self.words_per_row)),
                                    layer="metal2",
                                    offset=vector(br_out.lx(), 0),
                                    width=br_out.width(),
                                    height=self.route_height)

                self.add_cross_contact_center(cross_m1m2,
                                              offset=vector(bl_out.cx(),
                                                            bl_out_y + 0.5 * self.bus_width),
                                              rotate=True)
                self.add_cross_contact_center(cross_m1m2,
                                              offset=vector(br_out.cx(),
                                                            br_out_y + 0.5 * self.bus_width),
                                              rotate=True)

            else:
                pins = [bl_out, br_out]
                y_offsets = [bl_out_y, br_out_y]
                for i in range(2):
                    self.add_rect(layer=METAL2, width=bl_out.width(),
                                  offset=vector(pins[i].lx(), y_offsets[i] - cross_via_extension),
                                  height=self.route_height - y_offsets[i] + cross_via_extension)
                    # This via is on the right of the wire
                    self.add_cross_contact_center(cross_m1m2, rotate=True,
                                                  offset=vector(pins[i].cx(),
                                                                y_offsets[i]
                                                                + 0.5 * self.bus_width))
