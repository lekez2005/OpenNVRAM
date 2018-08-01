from math import log
import design
from tech import drc, parameter
import debug
import contact
from pinv import pinv
from pnand2 import pnand2
from pnand3 import pnand3
from pnor2 import pnor2
import math
from vector import vector
from globals import OPTS

class control_logic(design.design):
    """
    Dynamically generated Control logic for the total SRAM circuit.
    """

    def __init__(self, num_rows):
        """ Constructor """
        design.design.__init__(self, "control_logic")
        debug.info(1, "Creating {}".format(self.name))

        self.num_rows = num_rows
        self.m1m2_layers = ("metal1", "via1", "metal2")
        self.create_layout()
        self.DRC_LVS()

    def create_layout(self):
        """ Create layout and route between modules """
        self.create_modules()
        self.setup_layout_offsets()
        self.add_modules()
        self.calculate_dimensions()
        self.add_routing()
        self.add_layout_pins()

        self.add_lvs_correspondence_points()

    def create_modules(self):
        """ add all the required modules """
        input_lst =["csb","web","oeb","clk"]
        output_lst = ["s_en", "w_en", "tri_en", "tri_en_bar", "clk_bar", "clk_buf"]
        rails = ["vdd", "gnd"]
        for pin in input_lst + output_lst + rails:
            self.add_pin(pin)

        self.nand2 = pnand2()
        self.add_mod(self.nand2)
        self.nand3 = pnand3()
        self.add_mod(self.nand3)
        self.nor2 = pnor2()
        self.add_mod(self.nor2)

        # Special gates: inverters for buffering
        self.inv = pinv(1)
        self.add_mod(self.inv)
        self.inv1 = pinv(1, rail_offset=drc["implant_to_implant"])
        self.add_mod(self.inv1)
        self.inv2 = pinv(2)
        self.add_mod(self.inv2)
        self.inv4 = pinv(4)
        self.add_mod(self.inv4)
        self.inv8 = pinv(8)
        self.add_mod(self.inv8)
        self.inv16 = pinv(16)
        self.add_mod(self.inv16)

        c = reload(__import__(OPTS.ms_flop_array))
        ms_flop_array = getattr(c, OPTS.ms_flop_array)
        self.msf_control = ms_flop_array(name="msf_control",
                                         columns=3,
                                         word_size=3)
        self.add_mod(self.msf_control)

        c = reload(__import__(OPTS.replica_bitline))
        replica_bitline = getattr(c, OPTS.replica_bitline)
        # FIXME: These should be tuned according to the size!
        delay_stages = 4 # This should be even so that the delay line is inverting!
        delay_fanout = 3
        bitcell_loads = int(math.ceil(self.num_rows / 5.0))
        self.replica_bitline = replica_bitline(delay_stages, delay_fanout, bitcell_loads)
        self.add_mod(self.replica_bitline)


    def setup_layout_offsets(self):
        """ Setup layout offsets, determine the size of the busses etc """
        # These aren't for instantiating, but we use them to get the dimensions
        self.poly_contact_offset = vector(0.5*contact.poly.width,0.5*contact.poly.height)

        # M1/M2 routing pitch is based on contacted pitch
        self.m1_pitch = max(contact.m1m2.width,contact.m1m2.height) + max(drc["metal1_to_metal1"],drc["metal2_to_metal2"])
        self.m2_pitch = max(contact.m2m3.width,contact.m2m3.height) + max(drc["metal2_to_metal2"],drc["metal3_to_metal3"])

        # Have the cell gap leave enough room to route an M2 wire.
        # Some cells may have pwell/nwell spacing problems too when the wells are different heights.
        self.cell_gap = max(self.m2_pitch,drc["pwell_to_nwell"])

        # First RAIL Parameters: gnd, oe, oebar, cs, we, clk_buf, clk_bar
        self.rail_1_start_x = 0
        self.num_rails_1 = 8
        self.rail_1_names = ["clk_buf", "gnd", "oe_bar", "cs", "we", "vdd",  "oe", "clk_bar"]
        self.overall_rail_1_gap = (self.num_rails_1 + 2) * self.m2_pitch
        self.rail_1_x_offsets = {}

        # GAP between main control and replica bitline
        self.replica_bitline_gap = 2*self.m2_pitch

    def calculate_dimensions(self):
        self.height = self.clk_inv1.get_pin("vdd").uy()

        msf_right_x = self.msf_inst.rx()
        self.clk_bar_rail_x = msf_right_x + 2*self.m2_space
        self.clk_buf_rail_x = self.clk_bar_rail_x + self.wide_m1_space + 1.5*self.m2_width

        rbl_vdd_pins = self.rbl.get_pins("vdd")
        self.left_vdd = rbl_vdd_pins[0] if rbl_vdd_pins[0].lx() < rbl_vdd_pins[0].lx() else rbl_vdd_pins[1]
        self.right_vdd = rbl_vdd_pins[1] if rbl_vdd_pins[1].lx() > rbl_vdd_pins[0].lx() else rbl_vdd_pins[0]

        self.width = max(self.right_vdd.rx(), self.clk_buf_rail_x + 1.5*self.m2_width) +\
                     self.wide_m1_space + self.rail_height
        


    def add_modules(self):
        """ Place all the modules """
        self.add_rbl()
        self.add_rbl_buffer()
        self.add_blk()
        self.add_wen_buffer()
        self.add_wen()
        self.add_tri_en()
        self.add_tri_en_bar()
        self.add_control_flops()
        self.add_clk_buffer()

        


    def add_routing(self):
        """ Routing between modules """
        self.route_clk()
        self.route_msf()
        self.create_output_rails()
        self.route_tri_en_bar()
        self.route_tri_en()
        self.route_w_en()
        self.route_blk()
        self.route_vdd()
        self.route_gnd()

    def add_rbl(self):
        """ Add the replica bitline """

        # leave space below to connect left and right vdd
        gnd_y = self.replica_bitline.height - self.replica_bitline.get_pin("gnd").uy() # after mirror
        y_offset = gnd_y + 2*self.m1_space + self.rail_height

        self.replica_bitline_offset = vector(0 , y_offset)
        self.rbl=self.add_inst(name="replica_bitline",
                               mod=self.replica_bitline,
                               offset=self.replica_bitline_offset + vector(0, self.replica_bitline.height),
                               mirror="MX",
                               rotate=0)

        self.connect_inst(["rblk", "pre_s_en", "vdd", "gnd"])

    def add_rbl_buffer(self):
        y_space = 4*self.m1_space
        # extra m1_width added to x_space because some rails extend past the cells
        x_space = self.rail_height + 2*self.m1_space + self.m1_width
        # BUFFER INVERTERS FOR S_EN
        # input: input: pre_s_en_bar, output: s_en
        self.s_en_offset = self.replica_bitline_offset + vector(x_space, self.replica_bitline.height + y_space)
        self.s_en = self.add_inst(name="inv_s_en",
                                  mod=self.inv1,
                                  mirror="MY",
                                  offset=self.s_en_offset + vector(self.inv1.width, 0))
        self.connect_inst(["pre_s_en_bar", "s_en", "vdd", "gnd"])

        self.rbl_buffer_offset = self.s_en_offset + vector(self.inv1.width, 0)

        # input: pre_s_en, output: pre_s_en_bar
        self.pre_s_en_bar = self.add_inst(name="inv_pre_s_en_bar",
                                          mod=self.inv1,
                                          mirror="MY",
                                          offset=self.rbl_buffer_offset + vector(self.inv1.width, 0))
        self.connect_inst(["pre_s_en", "pre_s_en_bar", "vdd", "gnd"])



    def add_blk(self):

        # input: rblk_bar, output: rblk
        self.rblk_offset = self.s_en_offset + vector(0, self.inv1.height)
        self.rblk = self.add_inst(name="inv_rblk",
                                  mod=self.inv1,
                                  mirror="XY",
                                  offset=self.rblk_offset + vector(self.inv1.width, self.inv1.height))
        self.connect_inst(["rblk_bar", "rblk", "vdd", "gnd"])

        # input: OE, clk_bar,CS output: rblk_bar
        self.rblk_bar_offset = self.rblk_offset + vector(self.inv1.width, 0)
        self.rblk_bar = self.add_inst(name="nand3_rblk_bar",
                                      mod=self.nand3,
                                      mirror="XY",
                                      offset=self.rblk_bar_offset+vector(self.nand3.width, self.nand3.height))
        self.connect_inst(["clk_bar", "oe", "cs", "rblk_bar", "vdd", "gnd"])


    def add_wen_buffer(self):
        # BUFFER INVERTERS FOR W_EN
        # FIXME: Can we remove these two invs and size the previous one?
        self.pre_w_en_bar_offset = self.rblk_offset + vector(0, self.inv1.height)
        self.pre_w_en_bar = self.add_inst(name="inv_pre_w_en_bar",
                                          mod=self.inv1,
                                          offset=self.pre_w_en_bar_offset)
        self.connect_inst(["pre_w_en", "pre_w_en_bar", "vdd", "gnd"])

        self.w_en_offset = self.pre_w_en_bar_offset + vector(self.inv1.width, 0)
        self.w_en = self.add_inst(name="inv_w_en2",
                                  mod=self.inv1,
                                  offset=self.w_en_offset)
        self.connect_inst(["pre_w_en_bar", "w_en", "vdd", "gnd"])

    def add_wen(self):

        # input: w_en_bar, output: pre_w_en
        self.pre_w_en_offset = self.pre_w_en_bar_offset + vector(self.inv1.width, 2*self.inv.height)
        self.pre_w_en = self.add_inst(name="inv_pre_w_en",
                                      mod=self.inv1,
                                      mirror="XY",
                                      offset=self.pre_w_en_offset)
        self.connect_inst(["w_en_bar", "pre_w_en", "vdd", "gnd"])

        # input: WE, clk_bar, CS output: w_en_bar
        self.w_en_bar_offset = self.pre_w_en_offset + vector(self.nand3.width, 0)
        self.w_en_bar = self.add_inst(name="nand3_w_en_bar",
                                      mod=self.nand3,
                                      mirror="XY",
                                      offset=self.w_en_bar_offset)
        self.connect_inst(["clk_bar", "cs", "we", "w_en_bar", "vdd", "gnd"])

    def add_tri_en(self):
        # input: clk_buf, OE_bar output: tri_en
        y_space = drc["implant_to_implant"]
        self.tri_en_offset = self.pre_w_en_offset + vector(self.nor2.width-self.inv1.width, y_space)
        self.tri_en=self.add_inst(name="nor2_tri_en",
                                  mod=self.nor2,
                                  mirror="MY",
                                  offset=self.tri_en_offset)
        self.connect_inst(["clk_buf", "oe_bar", "tri_en", "vdd", "gnd"])

    def add_tri_en_bar(self):
        #y_space = drc["implant_to_implant"]
        y_space = 0
        self.tri_en_bar_offset = self.tri_en_offset + vector(self.nand2.width-self.nor2.width,
                                                             y_space + self.nand2.height+self.nor2.height)
        self.tri_en_bar = self.add_inst(name="nand2_tri_en",
                                        mod=self.nand2,
                                        offset=self.tri_en_bar_offset,
                                        mirror="XY")
        self.connect_inst(["clk_bar", "oe", "tri_en_bar", "vdd", "gnd"])

    def add_control_flops(self):
        """ Add the control signal flops for OEb, WEb, CSb. """
        self.h_rail_pitch = contact.m1m2.first_layer_height + self.wide_m1_space
        y_space = 2*self.wide_m1_space + 4*self.h_rail_pitch
        self.msf_offset = self.tri_en_bar_offset + vector(-self.nand2.width, y_space) +\
                          vector(0, self.msf_control.height)
        self.msf_inst=self.add_inst(name="msf_control",
                                    mod=self.msf_control,
                                    offset=self.msf_offset,
                                    mirror="MX",
                                    rotate=0)
        # don't change this order. This pins are meant for internal connection of msf array inside the control logic.
        # These pins are connecting the msf_array inside of control_logic.
        temp = ["oeb", "csb", "web",
                "oe_bar", "oe",
                "cs_bar", "cs",
                "we_bar", "we",
                "clk_buf", "vdd", "gnd"]
        self.connect_inst(temp)

    def add_clk_buffer(self):
        """ Add the multistage clock buffer below the control flops """
        y_space = 5*self.m1_pitch + self.rail_height
        # 4 stage clock buffer
        self.clk_bar_offset = self.msf_offset + vector(0, y_space)
        self.clk_bar = self.add_inst(name="inv_clk_bar",
                                     mod=self.inv8,
                                     offset=self.clk_bar_offset)
        self.connect_inst(["clk2", "clk_bar", "vdd", "gnd"])

        self.clk_buf_offset = self.clk_bar_offset + vector(self.inv8.width, 0)
        self.clk_buf = self.add_inst(name="inv_clk_buf",
                                     mod=self.inv16,
                                     offset=self.clk_buf_offset)
        self.connect_inst(["clk_bar", "clk_buf", "vdd", "gnd"])

        self.clk_inv1_offset = self.clk_bar_offset + vector(0, self.inv16.height + drc["implant_to_implant"])
        self.clk_inv1 = self.add_inst(name="inv_clk1_bar",
                                      mod=self.inv2,
                                      offset=self.clk_inv1_offset)
        self.connect_inst(["clk", "clk1_bar", "vdd", "gnd"])

        self.clk_inv2_offset = self.clk_inv1_offset + vector(self.inv2.width, 0)
        self.clk_inv2 = self.add_inst(name="inv_clk2",
                                      mod=self.inv4,
                                      offset=self.clk_inv2_offset)
        self.connect_inst(["clk1_bar", "clk2", "vdd", "gnd"])


    def route_clk(self):
        """ Route the clk and clk_bar signal internally """
        self.add_path("metal1", [self.clk_inv1.get_pin("Z").center(),
                                 vector(self.clk_inv2.get_pin("A").cx(), self.clk_inv1.get_pin("Z").cy())])

        inv2_z_pin = self.clk_inv2.get_pin("Z")
        contact_offset = vector(inv2_z_pin.rx()-0.5*contact.m1m2.first_layer_height, inv2_z_pin.cy())
        self.add_contact_center(layers=self.m1m2_layers, rotate=90, offset=contact_offset)
        inv2_gnd_pin = self.clk_inv2.get_pin("gnd")
        clk_bar_left = self.clk_bar.lx() + self.m2_space
        clk_bar_a_pin = self.clk_bar.get_pin("A")

        self.add_path("metal2", [vector(inv2_z_pin.rx()-0.5*self.m2_width, inv2_z_pin.by()),
                                 vector(inv2_z_pin.rx()-0.5*self.m2_width, inv2_gnd_pin.cy()),
                                 vector(clk_bar_left, inv2_gnd_pin.cy()),
                                 vector(clk_bar_left, clk_bar_a_pin.cy()),
                                 clk_bar_a_pin.center()])
        self.add_contact_center(layers=self.m1m2_layers, offset=clk_bar_a_pin.center())
        self.add_path("metal1", [self.clk_bar.get_pin("Z").center(),
                                 vector(self.clk_buf.get_pin("A").cx(), self.clk_bar.get_pin("Z").cy())])

        # add clk and clk_bar rails
        top = self.clk_bar.uy()
        bottom = self.rblk_bar.by()

        self.clk_bar_rail = self.left_clk_rail = self.add_rect("metal2", width=1.5*self.m2_width, height=top-bottom,
                                                               offset=vector(self.clk_bar_rail_x, bottom))
        self.clk_buf_rail = self.right_clk_rail = self.add_rect("metal2", width=1.5*self.m2_width, height=top-bottom,
                      offset=vector(self.clk_buf_rail_x, bottom))

        # route clk_bar to rail
        clk_bar_z = self.clk_bar.get_pin("Z")
        clk_bar_y_offset = self.clk_bar.get_pin("gnd").cy() -self.rail_height - 2*self.m2_space
        contact_offset = vector(clk_bar_z.rx() - 0.5*contact.m1m2.first_layer_height,
                                clk_bar_z.by()+0.5*contact.m1m2.first_layer_width)
        self.add_contact_center(self.m1m2_layers, contact_offset, rotate=90)
        contact_offset = vector(self.clk_buf.rx() + 2 * self.m1_space + contact.m1m2.second_layer_height,
                                clk_bar_y_offset + 0.5 * self.m2_space)
        self.add_path("metal2", [vector(clk_bar_z.rx()-0.5*self.m2_width, clk_bar_z.cy()),
                                 vector(clk_bar_z.rx()-0.5*self.m2_width, clk_bar_y_offset),
                                 vector(contact_offset.x, clk_bar_y_offset)])

        self.add_contact(self.m1m2_layers, rotate=270, offset=contact_offset)
        self.add_path("metal1", [vector(contact_offset.x, clk_bar_y_offset),
                                 vector(self.clk_bar_rail.offset.x+0.5*self.clk_bar_rail.width, clk_bar_y_offset)])
        contact_offset = vector(self.clk_bar_rail.offset.x + 0.5 * self.clk_bar_rail.width,
                                clk_bar_y_offset + 0.5 * contact.m1m2.first_layer_width)
        self.add_contact_center(self.m1m2_layers, contact_offset, rotate=0)

        # route clock buf to rail
        clk_z = self.clk_buf.get_pin("Z")
        contact_offset = vector(self.clk_buf_rail.offset.x + 0.5*self.clk_buf_rail.width,
                                clk_z.by()+0.5*contact.m1m2.first_layer_width)
        self.add_contact_center(self.m1m2_layers, contact_offset, rotate=0)
        self.add_path("metal1", [vector(clk_z.rx(), clk_z.cy()), vector(contact_offset.x, clk_z.cy())])

    def route_pin_to_rail(self, pin, rail_rect, y_pos, x_pos):
        self.add_contact_center(layers=self.m1m2_layers, offset=vector(rail_rect.offset.x + 0.5*rail_rect.width,
                                                                y_pos))
        self.add_rect("metal1", vector(x_pos, y_pos - 0.5*self.m1_width), height=self.m1_width,
                      width=rail_rect.offset.x + 0.5*rail_rect.width - x_pos)
        self.add_contact_center(layers=self.m1m2_layers, offset=vector(pin.cx(), y_pos), rotate=90)
        self.add_path("metal2", [vector(pin.cx(), y_pos), vector(pin.cx(), pin.cy())])

    def route_msf(self):
        rail_top = self.clk_bar_rail.uy()
        rail_bottom = self.msf_inst.uy() + 2*self.m2_space
        rail_height = rail_top - rail_bottom
        rail_width = self.m2_width
        rail_pitch = rail_width + self.wide_m1_space
        rail_offset = vector(self.clk_bar_rail.lx() - rail_pitch, rail_bottom)
        self.web_rail = self.add_rect("metal2", offset=rail_offset, height=rail_height, width=self.m2_width)
        self.csb_rail = self.add_rect("metal2", offset=rail_offset-vector(rail_pitch, -self.m1_pitch),
                                      height=rail_height-self.m1_pitch,
                                      width=self.m2_width)
        self.oeb_rail = self.add_rect("metal2", offset=rail_offset-vector(2*rail_pitch, -2*self.m1_pitch),
                                      height=rail_height-2*self.m1_pitch,
                                      width=self.m2_width)

        y_pos = self.msf_inst.uy() + self.m1_pitch
        self.route_pin_to_rail(self.msf_inst.get_pin("din[2]"), self.web_rail, y_pos, self.msf_inst.lx())
        self.route_pin_to_rail(self.msf_inst.get_pin("din[1]"), self.csb_rail, y_pos + self.m1_pitch, self.msf_inst.lx())
        self.route_pin_to_rail(self.msf_inst.get_pin("din[0]"), self.oeb_rail, y_pos + 2*self.m1_pitch, self.msf_inst.lx())

        msf_clk_pin = self.msf_inst.get_pin("clk")
        rail_left_x = self.clk_buf_rail.offset.x
        self.add_rect("metal1", width=rail_left_x + 1.5*self.m2_width - msf_clk_pin.rx(), height=msf_clk_pin.height(),
                      offset=msf_clk_pin.lr())
        self.add_contact_center(layers=self.m1m2_layers,
                                offset=vector(rail_left_x+0.75*self.m2_width, msf_clk_pin.by()+0.5*contact.m1m2.first_layer_height))

        # add msf output rails
        rail_width = self.m2_width
        rail_pitch = rail_width + self.wide_m1_space

        # rail_order from left to right is [oe_bar oe we cs]
        oe_bar_bottom = self.tri_en.get_pin("B").by()
        oe_bottom = self.rblk_bar.get_pin("B").by()
        we_bottom = self.w_en_bar.get_pin("C").by()
        cs_bottom = self.rblk_bar.get_pin("C").by()
        bottoms = [oe_bar_bottom, oe_bottom, we_bottom, cs_bottom]
        msf_outputs = [self.msf_inst.get_pin("dout[0]"), self.msf_inst.get_pin("dout_bar[0]"),
                       self.msf_inst.get_pin("dout_bar[2]"), self.msf_inst.get_pin("dout_bar[1]")]
        horizontal_rail_order = [3, 2, 0, 1]
        rail_x_offset = self.left_clk_rail.lx() - len(bottoms) * rail_pitch
        m1_y_offset = self.msf_inst.by() -2*self.wide_m1_space
        vrails = [None]*len(bottoms)
        for i in range(0, len(bottoms)):
            output_pin = msf_outputs[i]
            # vertical rail
            v_rail_offset = vector(rail_x_offset + i*rail_pitch, bottoms[i])
            h_rail_offset = vector(output_pin.lx(), m1_y_offset - horizontal_rail_order[i] * self.h_rail_pitch)

            rail_height = h_rail_offset.y + self.m1_width - bottoms[i]
            vrails[i] = self.add_rect("metal2", width=rail_width, height=rail_height, offset=v_rail_offset)

            # horizontal rail

            h_rail_width = v_rail_offset.x - output_pin.lx() + rail_width
            self.add_rect("metal1", offset=h_rail_offset, width=h_rail_width, height=rail_width)
            self.add_rect("metal2", offset=vector(output_pin.lx(), h_rail_offset.y),
                          height=output_pin.by()-h_rail_offset.y, width=output_pin.width())

            self.add_contact(layers=self.m1m2_layers, offset=vector(output_pin.lx(), h_rail_offset.y))
            self.add_contact(layers=self.m1m2_layers, offset=vector(
                v_rail_offset.x, h_rail_offset.y + self.m1_width - contact.m1m2.first_layer_height))

        (self.oe_bar_rail, self.oe_rail, self.we_rail, self.cs_rail) = vrails

    def create_output_rails(self):
        bottom = self.clk_bar_rail.by()
        tops = [self.tri_en_bar.get_pin("Z").uy(), self.tri_en.get_pin("Z").uy(),
                self.w_en.get_pin("Z").uy(), self.s_en.get_pin("vdd").uy()]
        rails = [None]*4
        rail_width = self.m2_width
        rail_pitch = rail_width + self.wide_m1_space
        for i in range(len(tops)):
            rails[i] = self.add_rect("metal2", height=tops[i]-bottom, width=rail_width,
                                     offset=vector(self.oe_bar_rail.lx() - (i+1)*rail_pitch, bottom))
        (self.en_bar_rail, self.en_rail, self.w_en_rail, self.s_en_rail) = rails


    def route_pin_to_vertical_rail(self, pin, rail, via_x_pos, pos="center", rail_cont="vertical"):
        rail_cx = rail.offset.x + 0.5*rail.width
        if rail_cont == "vertical":
            self.add_contact_center(layers=self.m1m2_layers, offset=vector(rail_cx, pin.cy()))
        else:
            self.add_contact(layers=self.m1m2_layers,
                             offset=vector(rail.rx(), pin.by()), rotate=90)
        self.add_rect("metal1", height=self.m1_width, offset=vector(via_x_pos, pin.by()),
                      width=rail_cx-via_x_pos)
        self.add_contact(layers=self.m1m2_layers, offset=vector(via_x_pos, pin.by()), rotate=90)
        self.add_rect("metal2", height=self.m2_width, offset=pin.ll(), width=via_x_pos-pin.lx())
        if pos == "center":
            via_y = pin.cy() - 0.5*contact.m1m2.second_layer_height
        elif pos == "top":
            via_y = pin.by()
        else:
            via_y = pin.uy() - contact.m1m2.second_layer_height
        self.add_contact(layers=self.m1m2_layers, offset=vector(pin.lx(), via_y))

    def route_tri_en_bar(self):
        via_x_pos = self.tri_en_bar.rx()
        self.route_pin_to_vertical_rail(self.tri_en_bar.get_pin("B"), self.oe_rail, via_x_pos, "top")
        self.route_pin_to_vertical_rail(self.tri_en_bar.get_pin("A"), self.clk_bar_rail, via_x_pos, "bottom")
        self.route_pin_to_vertical_rail(self.tri_en_bar.get_pin("Z"), self.en_bar_rail, via_x_pos+2*self.m1_space,
                                        "center", rail_cont="horizontal")

    def route_tri_en(self):
        via_x_pos = self.tri_en.rx()
        self.route_pin_to_vertical_rail(self.tri_en.get_pin("B"), self.oe_bar_rail, via_x_pos, "bottom")
        self.route_pin_to_vertical_rail(self.tri_en.get_pin("A"), self.clk_buf_rail, via_x_pos, "top")
        self.route_pin_to_vertical_rail(self.tri_en.get_pin("Z"), self.en_rail, via_x_pos + 2*self.m1_space,
                                        "center", rail_cont="horizontal")

    def route_w_en(self):
        via_x_pos = self.w_en_bar.rx()
        self.route_pin_to_vertical_rail(self.w_en_bar.get_pin("C"), self.we_rail, via_x_pos, "top")
        self.route_pin_to_vertical_rail(self.w_en_bar.get_pin("B"), self.cs_rail, via_x_pos, "center")
        self.route_pin_to_vertical_rail(self.w_en_bar.get_pin("A"), self.clk_bar_rail, via_x_pos, "bottom")
        w_en_z_pin = self.w_en.get_pin("Z")
        self.add_rect("metal1", offset=w_en_z_pin.lr(), width=self.w_en_rail.lx()-w_en_z_pin.rx())
        self.add_contact(layers=self.m1m2_layers, offset=vector(self.w_en_rail.rx(), w_en_z_pin.by()), rotate=90)


        pre_w_en_a_pin = self.pre_w_en.get_pin("A")
        wen_bar_z_pin = self.w_en_bar.get_pin("Z")

        self.add_rect("metal1", offset=pre_w_en_a_pin.lr(), height=self.m1_width, width=wen_bar_z_pin.lx()-pre_w_en_a_pin.rx())

        pre_w_en_z_pin = self.pre_w_en.get_pin("Z")
        self.add_contact_center(layers=self.m1m2_layers,
                                offset=vector(pre_w_en_z_pin.rx(), pre_w_en_z_pin.cy()))

        pre_w_en_bar_a_pin = self.pre_w_en_bar.get_pin("A")

        mid_x = self.pre_w_en.lx() + self.wide_m1_space
        self.add_path("metal2", [vector(pre_w_en_z_pin.rx(), pre_w_en_z_pin.cy()),
                                 vector(mid_x, pre_w_en_z_pin.cy()),
                                 vector(mid_x, pre_w_en_bar_a_pin.cy()),
                                 vector(pre_w_en_bar_a_pin.cx(), pre_w_en_bar_a_pin.cy())])
        self.add_contact_center(layers=self.m1m2_layers, offset=pre_w_en_bar_a_pin.center())

        pre_w_en_bar_z_pin = self.pre_w_en_bar.get_pin("Z")
        w_en_a_pin = self.w_en.get_pin("A")

        self.add_path("metal1", [vector(pre_w_en_bar_z_pin.lx(), pre_w_en_bar_z_pin.cy()),
                                 vector(w_en_a_pin.cx(), pre_w_en_bar_z_pin.cy())])

    def route_blk(self):
        via_x_pos = self.rblk_bar.rx()
        self.route_pin_to_vertical_rail(self.rblk_bar.get_pin("C"), self.cs_rail, via_x_pos, "top")
        self.route_pin_to_vertical_rail(self.rblk_bar.get_pin("B"), self.oe_rail, via_x_pos, "center")
        self.route_pin_to_vertical_rail(self.rblk_bar.get_pin("A"), self.clk_bar_rail, via_x_pos, "bottom")

        rblk_bar_z_pin = self.rblk_bar.get_pin("Z")
        rblk_a_pin = self.rblk.get_pin("A")
        self.add_path("metal1", [rblk_a_pin.center(), vector(rblk_bar_z_pin.cx(), rblk_a_pin.cy())])

        mid_x = self.rblk.lx() + self.wide_m1_space
        pre_s_en_bar_gnd = self.pre_s_en_bar.get_pin("gnd")
        mid_y = pre_s_en_bar_gnd.cy()
        rblk_z_pin = self.rblk.get_pin("Z")
        en_pin = self.rbl.get_pin("en")
        self.add_contact_center(layers=self.m1m2_layers,
                                offset=vector(rblk_z_pin.rx(), rblk_z_pin.cy()))
        self.add_path("metal2", [vector(rblk_z_pin.rx(), rblk_z_pin.cy()),
                                 vector(mid_x, rblk_z_pin.cy()),
                                 vector(mid_x, mid_y),
                                 vector(en_pin.cx(), mid_y),
                                 vector(en_pin.cx(), en_pin.by())])

        # rbl out to buffer input
        pre_s_en_bar_a_pin = self.pre_s_en_bar.get_pin("A")
        rbl_out_pin = self.rbl.get_pin("out")

        self.add_contact(layers=self.m1m2_layers, offset=vector(rbl_out_pin.lx(),
                                                                rbl_out_pin.uy() - contact.m1m2.first_layer_height))
        self.add_path("metal2", [vector(rbl_out_pin.cx(), pre_s_en_bar_a_pin.cy()),
                                 vector(rbl_out_pin.cx(), rbl_out_pin.uy())])

        self.add_path("metal1", [vector(pre_s_en_bar_a_pin.center()),
                                 vector(rbl_out_pin.cx(), pre_s_en_bar_a_pin.cy())])

        self.add_contact(layers=self.m1m2_layers, offset=vector(rbl_out_pin.rx(),pre_s_en_bar_a_pin.by()),
                         rotate=90)

        pre_s_en_bar_z_pin = self.pre_s_en_bar.get_pin("Z")
        s_en_a_pin = self.s_en.get_pin("A")
        self.add_path("metal1", [s_en_a_pin.center(), vector(pre_s_en_bar_z_pin.lx(), s_en_a_pin.cy())])

        s_en_z_pin = self.s_en.get_pin("Z")
        self.add_contact_center(layers=self.m1m2_layers, offset=vector(s_en_z_pin.rx(),
                                                                s_en_z_pin.cy()))
        s_en_vdd = self.s_en.get_pin("vdd")
        self.add_path("metal2", [vector(s_en_z_pin.rx()-0.5*self.m2_width, s_en_z_pin.cy()),
                                 vector(self.s_en.rx(), s_en_z_pin.cy()),
                                 vector(self.s_en.rx(), s_en_vdd.cy()),
                                 vector(self.s_en_rail.rx(), s_en_vdd.cy())])



    def pin_to_vdd(self, pin, vdd):
        self.add_rect("metal1", height=pin.height(), width=pin.lx()-vdd.rx(), offset=vector(vdd.rx(), pin.by()))

    def route_vdd(self):
        # extend left vdd to top
        self.vdd_rect = self.add_rect("metal1", offset=self.left_vdd.ul(),
                                      width=self.rail_height, height=self.height-self.left_vdd.uy())
        self.pin_to_vdd(self.s_en.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.rblk.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.pre_w_en_bar.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.pre_w_en.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.tri_en.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.tri_en_bar.get_pin("vdd"), self.left_vdd)

        for pin in self.msf_inst.get_pins("vdd"):
            if pin.layer == "metal1":
                self.pin_to_vdd(pin, self.left_vdd)

        self.pin_to_vdd(self.clk_bar.get_pin("vdd"), self.left_vdd)
        self.pin_to_vdd(self.clk_inv1.get_pin("vdd"), self.left_vdd)

        self.add_rect("metal1", height=self.rail_height, width=self.right_vdd.lx() - self.left_vdd.lx(),
                      offset=vector(0, 0))
        self.add_rect("metal1", height=self.left_vdd.by(), width=self.rail_height, offset=vector(0, 0))
        self.add_rect("metal1", height=self.right_vdd.by(), width=self.rail_height,
                      offset=vector(self.right_vdd.lx(), 0))

    def pin_to_gnd(self, pin, gnd):
        self.add_rect("metal1", height=pin.height(), width=gnd.lx()-pin.rx(), offset=vector(pin.rx(), pin.by()))

    def route_gnd(self):
        # create rail to the right
        rbl_buffer_gnd = self.s_en.get_pin("gnd")
        self.gnd_rail = self.add_rect("metal1", width=self.rail_height, height=self.height-rbl_buffer_gnd.by(),
                      offset=vector(self.width-self.rail_height, rbl_buffer_gnd.by()))
        rbl_gnd = self.rbl.get_pin("gnd")
        self.add_rect("metal1", width=self.rail_height, height=rbl_buffer_gnd.by()-rbl_gnd.uy(),
                      offset=rbl_gnd.ul())

        self.pin_to_gnd(rbl_buffer_gnd, self.gnd_rail)
        self.pin_to_gnd(self.rblk.get_pin("gnd"), self.gnd_rail)
        self.pin_to_gnd(self.pre_w_en_bar.get_pin("gnd"), self.gnd_rail)
        self.pin_to_gnd(self.pre_w_en.get_pin("gnd"), self.gnd_rail)
        self.pin_to_gnd(self.tri_en.get_pin("gnd"), self.gnd_rail)
        self.pin_to_gnd(self.tri_en_bar.get_pin("gnd"), self.gnd_rail)

        for pin in self.msf_inst.get_pins("gnd"):
            if pin.layer == "metal1":
                self.pin_to_gnd(pin, self.gnd_rail)

        self.pin_to_vdd(self.clk_bar.get_pin("gnd"), self.gnd_rail)
        self.pin_to_vdd(self.clk_inv1.get_pin("gnd"), self.gnd_rail)

    def add_pin_to_top(self, text, layer, rail, height):
        pin_offset = vector(rail.lx(), rail.uy()-height)
        self.add_layout_pin(text=text, layer=layer,
                            width=rail.width,
                            height=height,
                            offset=pin_offset)

    def add_pin_to_bottom(self, text, layer, rail, height):
        pin_offset = vector(rail.lx(), rail.by())
        self.add_layout_pin(text=text, layer=layer,
                            width=rail.width,
                            height=height,
                            offset=pin_offset)

    def add_layout_pins(self):
        """ Add the input/output layout pins. """
        self.add_pin_to_top("vdd", "metal1", self.vdd_rect, 2*self.m1_width)
        self.add_pin_to_top("gnd", "metal1", self.gnd_rail, 2*self.m1_width)

        # control inputs
        self.add_pin_to_top("web", "metal2", self.web_rail, 2*self.m1_width)
        self.add_pin_to_top("csb", "metal2", self.csb_rail, 2*self.m1_width)
        self.add_pin_to_top("oeb", "metal2", self.oeb_rail, 2*self.m1_width)

        # clock input
        clk_inv_a_pin = self.clk_inv1.get_pin("A")
        self.add_contact_center(layers=self.m1m2_layers, offset=clk_inv_a_pin.center())
        clk_in_x_offset = self.vdd_rect.rx() + self.m1_space
        self.add_rect("metal2", height=self.m2_width, width=clk_inv_a_pin.cx()-clk_in_x_offset,
                      offset=vector(clk_in_x_offset, clk_inv_a_pin.by()))
        clk_rect = self.add_rect(layer="metal2",
                            width=self.m2_width,
                            height=self.height-clk_inv_a_pin.by(),
                            offset=vector(clk_in_x_offset, clk_inv_a_pin.by()))
        self.add_pin_to_top("clk", "metal2", clk_rect, 2 * self.m1_width)

        # clock outputs
        self.add_pin_to_bottom("clk_buf", "metal2", self.clk_buf_rail, 2 * self.m1_width)
        self.add_pin_to_bottom("clk_bar", "metal2", self.clk_bar_rail, 2 * self.m1_width)
        # control outputs
        self.add_pin_to_bottom("s_en", "metal2", self.s_en_rail, 2 * self.m1_width)
        self.add_pin_to_bottom("w_en", "metal2", self.w_en_rail, 2 * self.m1_width)
        self.add_pin_to_bottom("tri_en", "metal2", self.en_rail, 2 * self.m1_width)
        self.add_pin_to_bottom("tri_en_bar", "metal2", self.en_bar_rail, 2 * self.m1_width)


    def add_lvs_correspondence_points(self):
        """ This adds some points for easier debugging if LVS goes wrong. 
        These should probably be turned off by default though, since extraction
        will show these as ports in the extracted netlist.
        """
        pin=self.clk_inv1.get_pin("Z")
        self.add_label_pin(text="clk1_bar",
                           layer="metal1",
                           offset=pin.ll(),
                           height=pin.height(),
                           width=pin.width())

        pin=self.clk_inv2.get_pin("Z")
        self.add_label_pin(text="clk2",
                           layer="metal1",
                           offset=pin.ll(),
                           height=pin.height(),
                           width=pin.width())

        pin=self.rbl.get_pin("out")
        self.add_label_pin(text="pre_s_en",
                           layer="metal1",
                           offset=pin.ll(),
                           height=pin.height(),
                           width=pin.width())


