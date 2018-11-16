import body_tap
import debug
import design
from tech import drc, spice
from vector import vector
from globals import OPTS
import utils



class bitcell_array(design.design):
    """
    Creates a rows x cols array of memory cells. Assumes bit-lines
    and word line is connected by abutment.
    Connects the word lines and bit lines.
    """

    def __init__(self, cols, rows, name="bitcell_array"):
        design.design.__init__(self, name)
        debug.info(1, "Creating {0} {1} x {2}".format(self.name, rows, cols))


        self.column_size = cols
        self.row_size = rows

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.cell = self.mod_bitcell()
        self.add_mod(self.cell)

        if OPTS.use_body_taps:
            self.body_tap = body_tap.body_tap()
            self.add_mod(self.body_tap)

        self.height = self.row_size*self.cell.height

        self.add_pins()
        self.create_layout()
        self.add_dummies()
        self.add_layout_pins()
        self.DRC_LVS()

    def add_pins(self):
        for col in range(self.column_size):
            self.add_pin("bl[{0}]".format(col))
            self.add_pin("br[{0}]".format(col))
        for row in range(self.row_size):
            self.add_pin("wl[{0}]".format(row))
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        (self.bitcell_offsets, tap_offsets) = utils.get_tap_positions(self.column_size)
        self.width = self.bitcell_offsets[-1] + self.cell.width
        if len(tap_offsets) > 0:
            self.add_left_dummy = False
            if tap_offsets[-1] < self.bitcell_offsets[-1]:  # add right dummy
                self.add_right_dummy = True
            else:
                self.add_right_dummy = False
                self.width = tap_offsets[-1] + self.body_tap.width


        self.cell_inst = {}
        yoffset = 0.0
        for row in range(self.row_size):

            if row % 2 == 0:
                tempy = yoffset + self.cell.height
                dir_key = "MX"
            else:
                tempy = yoffset
                dir_key = ""
            for col in range(self.column_size):
                name = "bit_r{0}_c{1}".format(row, col)



                self.cell_inst[row,col]=self.add_inst(name=name,
                                                      mod=self.cell,
                                                      offset=[self.bitcell_offsets[col], tempy],
                                                      mirror=dir_key)
                self.connect_inst(["bl[{0}]".format(col),
                                   "br[{0}]".format(col),
                                   "wl[{0}]".format(row),
                                   "vdd",
                                   "gnd"])
            for x_offset in tap_offsets:
                self.add_inst(name=self.body_tap.name, mod=self.body_tap, offset=vector(x_offset, tempy),
                              mirror=dir_key)
                self.connect_inst([])

            yoffset += self.cell.height


    def add_dummies(self):

        leftmost, rightmost = self.get_dummy_poly(self.cell, from_gds=True)
        poly_pitch = self.poly_width + self.poly_space
        x_offsets = []
        if self.add_left_dummy:
            x_offsets.append(leftmost - poly_pitch)
        if self.add_right_dummy:
            x_offsets.append(self.width + (self.cell.width - rightmost) + poly_pitch)
        cell_fills = self.get_poly_fills(self.cell)
        left_dummies = cell_fills["left"]
        dummy_height = left_dummies[0][1][1] - left_dummies[0][0][1]
        for i in range(self.row_size):
            y_base = i * self.cell.height
            if i % 2 == 0:
                y_offset = y_base + self.cell.height - left_dummies[0][1][1]
            else:
                y_offset = y_base + left_dummies[0][0][1]
            for x_offset in x_offsets:
                self.add_rect("po_dummy", offset=vector(x_offset, y_offset), width=self.poly_width,
                              height=dummy_height)



    def add_layout_pins(self):
        
        # Our cells have multiple gnd pins for now.
        # FIXME: fix for multiple vdd too
        vdd_pin = self.cell.get_pin("vdd")

        # shift it up by the overlap amount (gnd_pin) too
        # must find the lower gnd pin to determine this overlap
        lower_y = self.cell.height
        gnd_pins = self.cell.get_pins("gnd")
        for gnd_pin in gnd_pins:
            if gnd_pin.layer=="metal2" and gnd_pin.by()<lower_y:
                lower_y=gnd_pin.by()

        # lower_y is negative, so subtract off double this amount for each pair of
        # overlapping cells
        full_height = self.height - 2*lower_y
        
        vdd_pin = self.cell.get_pin("vdd")
        lower_x = vdd_pin.lx()
        # lower_x is negative, so subtract off double this amount for each pair of
        # overlapping cells
        full_width = self.width - 2*lower_x
        
        offset = vector(0.0, 0.0)
        for col in range(self.column_size):
            # get the pin of the lower row cell and make it the full width
            bl_pin = self.cell_inst[0,col].get_pin("BL")
            br_pin = self.cell_inst[0,col].get_pin("BR")
            self.add_layout_pin(text="bl[{0}]".format(col),
                                layer="metal2",
                                offset=bl_pin.ll(),
                                width=bl_pin.width(),
                                height=full_height)
            self.add_layout_pin(text="br[{0}]".format(col),
                                layer="metal2",
                                offset=br_pin.ll(),
                                width=br_pin.width(),
                                height=full_height)

            # gnd offset is 0 in our cell, but it be non-zero
            gnd_pins = self.cell_inst[0,col].get_pins("gnd")
            for gnd_pin in gnd_pins:
                # avoid duplicates by only doing even rows
                # also skip if it isn't the pin that spans the entire cell down to the bottom
                if gnd_pin.layer=="metal2" and gnd_pin.by()==lower_y:
                    self.add_layout_pin(text="gnd", 
                                        layer="metal2",
                                        offset=gnd_pin.ll(),
                                        width=gnd_pin.width(),
                                        height=full_height)
                    
            # increments to the next column width
            offset.x += self.cell.width

        offset.x = 0.0
        for row in range(self.row_size):
            wl_pin = self.cell_inst[row,0].get_pin("WL")
            vdd_pins = self.cell_inst[row,0].get_pins("vdd")
            gnd_pins = self.cell_inst[row,0].get_pins("gnd")

            for gnd_pin in gnd_pins:
                # only add to even rows
                if gnd_pin.layer=="metal1":
                    self.add_layout_pin(text="gnd", 
                                        layer="metal1",
                                        offset=gnd_pin.ll(),
                                        width=full_width - gnd_pin.lx(),
                                        height=gnd_pin.height())
                
            # add vdd label and offset
            # only add to odd rows to avoid duplicates
            for vdd_pin in vdd_pins:
                if (row % 2 == 1 or row == 0) and vdd_pin.layer=="metal1":
                    self.add_layout_pin(text="vdd",
                                        layer="metal1",
                                        offset=vdd_pin.ll(),
                                        width=full_width - vdd_pin.lx(),
                                        height=vdd_pin.height())
                
            # add wl label and offset
            self.add_layout_pin(text="wl[{0}]".format(row),
                                layer="metal1",
                                offset=wl_pin.ll(),
                                width=wl_pin.width()*self.column_size,
                                height=wl_pin.height())

            # increments to the next row height
            offset.y += self.cell.height

    def analytical_delay(self, slew, load=0):
        from tech import drc
        wl_wire = self.gen_wl_wire()
        wl_wire.return_delay_over_wire(slew)

        wl_to_cell_delay = wl_wire.return_delay_over_wire(slew)
        # hypothetical delay from cell to bl end without sense amp
        bl_wire = self.gen_bl_wire()
        cell_load = 2 * bl_wire.return_input_cap() # we ingore the wire r
                                                   # hence just use the whole c
        bl_swing = 0.1
        cell_delay = self.cell.analytical_delay(wl_to_cell_delay.slew, cell_load, swing = bl_swing)

        #we do not consider the delay over the wire for now
        return self.return_delay(cell_delay.delay+wl_to_cell_delay.delay,
                                 wl_to_cell_delay.slew)
                        
    def analytical_power(self, proc, vdd, temp, load):
        """Power of Bitcell array and bitline in nW."""
        from tech import drc
        
        # Dynamic Power from Bitline
        bl_wire = self.gen_bl_wire()
        cell_load = 2 * bl_wire.return_input_cap() 
        bl_swing = 0.1 #This should probably be defined in the tech file or input
        freq = spice["default_event_rate"]
        bitline_dynamic = bl_swing*cell_load*vdd*vdd*freq #not sure if calculation is correct
        
        #Calculate the bitcell power which currently only includes leakage 
        cell_power = self.cell.analytical_power(proc, vdd, temp, load)
        
        #Leakage power grows with entire array and bitlines.
        total_power = self.return_power(cell_power.dynamic + bitline_dynamic * self.column_size,
                                        cell_power.leakage * self.column_size * self.row_size)
        return total_power

    def gen_wl_wire(self):
        wl_wire = self.generate_rc_net(int(self.column_size), self.width, drc["minwidth_metal1"])
        wl_wire.wire_c = 2*spice["min_tx_gate_c"] + wl_wire.wire_c # 2 access tx gate per cell
        return wl_wire

    def gen_bl_wire(self):
        bl_pos = 0
        bl_wire = self.generate_rc_net(int(self.row_size-bl_pos), self.height, drc["minwidth_metal1"])
        bl_wire.wire_c =spice["min_tx_drain_c"] + bl_wire.wire_c # 1 access tx d/s per cell
        return bl_wire

    def output_load(self, bl_pos=0):
        bl_wire = self.gen_bl_wire()
        return bl_wire.wire_c # sense amp only need to charge small portion of the bl
                              # set as one segment for now

    def input_load(self):
        wl_wire = self.gen_wl_wire()
        return wl_wire.return_input_cap()
