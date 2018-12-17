import contact
import control_logic
from globals import OPTS
import utils
from vector import vector


class cam_control_logic(control_logic.control_logic):

    def create_layout(self):
        """ Create layout and route between modules """
        self.create_modules()
        self.setup_layout_offsets()
        self.add_modules()
        self.calculate_rail_positions()
        self.add_routing()
        self.add_layout_pins()

    def add_modules(self):
        self.add_rbl()
        self.add_rbl_buffer()
        self.add_blk()
        self.add_wen_buffer()
        self.add_wen()
        self.add_search_en()
        self.add_matchline_chb()
        self.add_latch_tags()
        self.add_mw_en()
        self.add_clk_bar_cs()
        self.add_sel_all_rows()
        self.add_sel_all_banks()

        self.add_control_flops()
        self.add_clk_buffer()

        self.height = self.clk_inv1.uy() + self.rail_height + self.parallel_line_space

    def add_routing(self):
        self.bottom_outputs = self.s_en.get_pin("A").cy()
        self.route_clk()
        self.route_se_neg_ff()
        self.route_oeb_csb_web()
        self.route_seb_mwb_bcast()
        self.route_sel_all_banks()
        self.route_sel_all_rows()
        self.route_clk_bar_cs()
        self.route_mw_en()
        self.route_latch_tags()
        self.route_matchline_chb()
        self.route_search_en()
        self.route_w_en()
        self.route_blk()
        self.route_power()

    def calculate_dimensions(self):
        pass

    def add_layout_pins(self):
        sorted_names = sorted(self.output_names, key=lambda x: self.rails[x])
        a, b = sorted_names.index('search_en'), sorted_names.index('latch_tags')
        sorted_names[b], sorted_names[a] = sorted_names[a], sorted_names[b]
        pin_height = 2*self.m3_width
        y_base = self.bottom_outputs + 2*self.m2_width
        for i in range(len(sorted_names)):
            pin_name = sorted_names[i]
            y_offset = y_base - i*self.v_rail_pitch
            x_offset = self.left_vdd.rx() + self.wide_m1_space + i*self.v_rail_pitch
            rail_x = self.rails[pin_name]

            self.add_rect("metal2", offset=vector(rail_x, y_offset), height=self.bottom_outputs - y_offset)

            self.add_rect("metal3", offset=vector(x_offset, y_offset), width=rail_x - x_offset)
            if pin_name in ["search_en", "sel_all_rows"]:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(rail_x + self.m2_width, y_offset), rotate=90)
            elif pin_name == "sel_all_rows":
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(rail_x + self.m2_width + contact.m2m3.second_layer_height, y_offset),
                                 rotate=90)
            else:
                self.add_contact(contact.m2m3.layer_stack, offset=vector(rail_x, y_offset))
            self.add_layout_pin(pin_name, "metal3", offset=vector(x_offset, y_offset - pin_height),
                                height=pin_height)



    def add_pins(self):
        input_lst = ["csb", "web", "oeb", "seb", "mwb", "bcastb", "clk"]
        self.output_names = ["clk_buf", "s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows",
                      "latch_tags", "matchline_chb"]
        power_pins = ["vdd", "gnd"]
        for pin in input_lst + self.output_names + power_pins:
            self.add_pin(pin)

    def create_flops(self):
        c = reload(__import__(OPTS.ms_flop_array))
        ms_flop_array = getattr(c, OPTS.ms_flop_array)
        self.flops_3_x = ms_flop_array(name="flops_3_x", columns=3, word_size=3)
        self.add_mod(self.flops_3_x)

        self.msf_control = ms_flop_array(name="flops_1_x",
                                       columns=1,
                                       word_size=1)
        self.add_mod(self.msf_control)



    def add_wen(self):
        """wen is enabled for either write or multi-write"""

        # AND of mw_we and clk_bar_cs
        offset = self.w_en_buffer.ul() + vector(self.inv1.width, self.inv1.height)
        self.pre_w_en = self.add_inst("pre_w_en", mod=self.inv1, offset=offset, mirror="XY")
        self.connect_inst(["pre_w_en_bar", "pre_w_en", "vdd", "gnd"])
        offset = self.pre_w_en.ur() + vector(self.nand2.width, 0)
        self.pre_w_en_bar = self.add_inst("pre_w_en_bar", mod=self.nand2, offset=offset, mirror="XY")
        self.connect_inst(["mw_we", "clk_bar_cs", "pre_w_en_bar", "vdd", "gnd"])

        # OR of mw_bar and we_bar to form mw_we
        offset = self.pre_w_en.ul() + vector(self.inv1.width, 0)
        self.mw_we = self.add_inst("mw_we", mod=self.inv1, offset=offset, mirror="MY")
        self.connect_inst(["mw_we_bar", "mw_we", "vdd", "gnd"])
        offset = self.mw_we.lr() + vector(self.nor2.width, 0)
        self.mw_we_bar = self.add_inst("mw_we_bar", mod=self.nor2, offset=offset, mirror="MY")
        self.connect_inst(["mw", "we", "mw_we_bar", "vdd", "gnd"])

    def add_search_en(self):
        """search_en = se AND clk_bar"""

        #  buffer
        offset = self.mw_we.ul() + vector(0, self.logic_buffer.height)
        self.search_en_buffer = self.add_inst("search_en_buffer", mod=self.logic_buffer, offset=offset, mirror="MX")
        self.connect_inst(["pre_search_en", "search_en", "vdd", "gnd"])

        offset = self.search_en_buffer.ul() + vector(self.inv1.width, 0)
        self.pre_search_en = self.add_inst("pre_search_en", mod=self.inv1, offset=offset, mirror="MY")
        self.connect_inst(["pre_search_en_bar", "pre_search_en", "vdd", "gnd"])
        offset = self.pre_search_en.lr() + vector(self.nand2.width, 0)
        self.pre_search_en_bar = self.add_inst("pre_search_en_bar", mod=self.nand2, offset=offset, mirror="MY")
        self.connect_inst(["clk_bar_cs", "se", "pre_search_en_bar", "vdd", "gnd"])

    def add_matchline_chb(self):
        """chb =  se nand clk"""
        offset = self.pre_search_en.ul() + vector(0, self.logic_buffer.height)
        self.ml_chb_buffer = self.add_inst("ml_buffer", mod=self.logic_buffer, offset=offset, mirror="MX")
        self.connect_inst(["pre_ml_chb", "matchline_chb", "vdd", "gnd"])

        offset = self.ml_chb_buffer.ul() + vector(self.nand3.width, 0)
        self.pre_ml_chb = self.add_inst("pre_ml_chb", mod=self.nand2, offset=offset, mirror="MY")
        self.connect_inst(["se", "clk_buf", "pre_ml_chb", "vdd", "gnd"])

    def add_latch_tags(self):
        """latch tags is neg edge ff output of se and clk_buf"""
        # buffer
        offset = self.pre_ml_chb.ul() + vector(0, self.logic_buffer.height)
        self.latch_tags_buffer = self.add_inst("latch_tags_buffer", mod=self.logic_buffer, offset=offset, mirror="MX")
        self.connect_inst(["pre_latch_tags", "latch_tags", "vdd", "gnd"])

        offset = self.latch_tags_buffer.ul() + vector(self.inv1.width, 0)
        self.pre_latch_tags = self.add_inst("pre_latch_tags", mod=self.inv1, offset=offset, mirror="MY")
        self.connect_inst(["pre_latch_tags_bar", "pre_latch_tags", "vdd", "gnd"])

        offset = self.pre_latch_tags.lr() + vector(self.nand2.width, 0)
        self.pre_latch_tags_bar = self.add_inst("pre_latch_tags_bar", mod=self.nand2, offset=offset, mirror="MY")
        self.connect_inst(["clk_buf ", "se_neg_ff", "pre_latch_tags_bar", "vdd", "gnd"])

    def add_mw_en(self):
        offset = self.pre_latch_tags.ul() + vector(0, self.logic_buffer.height)
        self.mw_buffer = self.add_inst("mw_buffer", mod=self.logic_buffer, offset=offset, mirror="MX")
        self.connect_inst(["mw", "mw_en", "vdd", "gnd"])

    def add_clk_bar_cs(self):
        """cs_bar and cs"""

        offset = self.mw_buffer.ul() + vector(self.inv2.width, 0)
        self.clk_bar_cs = self.add_inst("clk_bar_cs", mod=self.inv2, offset=offset, mirror="MY")
        self.connect_inst(["clk_bar_cs_bar", "clk_bar_cs", "vdd", "gnd"])

        offset = self.clk_bar_cs.lr() + vector(self.nand2.width, 0)
        self.clk_bar_cs_bar = self.add_inst("clk_bar_cs_bar", mod=self.nand2, offset=offset, mirror="MY")
        self.connect_inst(["cs", "clk_bar", "clk_bar_cs_bar", "vdd", "gnd"])

    def add_sel_all_rows(self):
        """broadcast"""
        offset = self.clk_bar_cs.ul() + vector(0, self.logic_buffer.height)
        self.broadcast_buffer = self.add_inst("broadcast_buffer", mod=self.logic_buffer, offset=offset, mirror="MX")
        self.connect_inst(["bcast", "sel_all_rows", "vdd", "gnd"])

    def add_sel_all_banks(self):
        """se or mw or broadcast"""
        offset = self.broadcast_buffer.ul()
        self.sel_all_banks_buffer = self.add_inst("sel_all_banks_buf", mod=self.logic_buffer_cont_pwell, offset=offset)
        self.connect_inst(["sel_all_banks_bar", "sel_all_banks", "vdd", "gnd"])

        offset = self.sel_all_banks_buffer.ul() + vector(self.nand3.width, self.nand3.height)
        self.sel_all_banks_bar = self.add_inst("sel_all_banks_bar", mod=self.nand3, offset=offset, mirror="XY")
        self.connect_inst(["se_bar", "mw_bar", "bcast_bar", "sel_all_banks_bar", "vdd", "gnd"])

    def add_control_flops(self):
        """ Add the control signal flops for OEb, WEb, CSb se_b mwb bcastb"""

        self.msf_bottom_gnd = max(self.flops_3_x.get_pins("gnd"), key=lambda x: x.uy())
        gnd_extension = self.msf_bottom_gnd.uy() - self.flops_3_x.height

        # seb_mwb_bcast
        self.h_rail_pitch = contact.m1m2.first_layer_width + self.m1_space
        y_space = utils.ceil(0.5*self.clk_bar_cs_bar.get_pin("gnd").height() + self.parallel_line_space +
                  6*self.h_rail_pitch + 0.5*self.msf_bottom_gnd.height())
        offset = self.sel_all_banks_bar.ul() + vector(0, y_space + self.flops_3_x.height)

        self.seb_mwb_bcast_inst = self.add_inst("seb_mwb_bcast", mod=self.flops_3_x, offset=offset, mirror="MX")
        self.connect_inst(["bcastb", "mwb", "seb", "bcast_bar", "bcast", "mw_bar", "mw", "se_bar", "se",
                           "clk_buf", "vdd", "gnd"])

        # oeb csb web

        via_space = self.m1_space + self.m1_width
        self.oeb_input_spaces = [self.parallel_line_space, via_space, via_space]

        y_space = 2*sum(self.oeb_input_spaces) + self.m2_space + self.line_end_space + contact.m1m2.second_layer_height
        offset = self.seb_mwb_bcast_inst.ul() + vector(0, y_space)
        self.oeb_csb_web_inst = self.add_inst(name="oeb_csb_web",
                                              mod=self.flops_3_x,
                                              offset=offset + vector(0, self.flops_3_x.height),
                                              mirror="MX",
                                              rotate=0)

        temp = ["web", "csb", "oeb",
                "we_bar", "we",
                "cs_bar", "cs",
                "oe_bar", "oe",
                "clk_buf", "vdd", "gnd"]
        self.connect_inst(temp)

        # seb neg ff

        self.se_neg_ff_bottom_space = gnd_extension + self.line_end_space + contact.m1m2.second_layer_height
        via_space = self.m1_space + self.m1_width
        self.oeb_input_spaces = [self.parallel_line_space, via_space, via_space]
        y_space = self.se_neg_ff_bottom_space + sum(self.oeb_input_spaces) + via_space

        self.msf_offset = self.oeb_csb_web_inst.ul() + vector(0, y_space)
        offset = self.msf_offset + vector(0, self.msf_control.height)

        self.se_neg_ff = self.add_inst("se_neg_ff", mod=self.msf_control, offset=offset, mirror="MX")
        self.connect_inst(["seb", "se_neg_ff_bar", "se_neg_ff", "clk_bar", "vdd", "gnd"])

    def get_ff_clk_buffer_space(self):
        return 2*self.line_end_space + contact.m1m2.second_layer_height + 0.5*self.rail_height


    def calculate_rail_positions(self):

        self.rails = {}

        rail_names = [
                ["clk", "mw_en"],
                ["bcast_bar", "sel_all_banks"],
                ["mw_bar", "clk_bar_cs"],
                ["se_bar", "matchline_chb"],

                ["se", "search_en"],
                ["mw"],
                ["bcast", "sel_all_rows"],

                ["se_neg_ff", "latch_tags"],

                ["we", "w_en"],
                ["cs"],
                ["oe", "s_en"],

                ["clk_bar"],
                ["clk_buf"]
            ]
        self.v_rail_pitch = self.m2_width + self.parallel_line_space
        flop_rail_start = self.oeb_csb_web_inst.rx() + contact.m1m2.second_layer_height + 2*self.line_end_space
        self.rail_start = (flop_rail_start + (len(["csb", "web", "oeb", "seb", "mwb", "bcastb", "se_neg_ff"])
                           - len(rail_names)) * self.v_rail_pitch)
        rail_x = self.rail_start
        for rail_name_list in rail_names:
            for name in rail_name_list:
                self.rails[name] = rail_x
            rail_x += self.v_rail_pitch

        self.clk_bar_rail_x = self.rails["clk_bar"]
        self.clk_buf_rail_x = self.rails["clk_buf"]
        self.cs_rail = self.rails["cs"]
        self.oe_rail = self.rails["oe"]
        self.s_en_rail = self.rails["s_en"]

        # vdd and gnd
        [self.left_vdd, self.right_vdd] = sorted(self.rbl.get_pins("vdd"), key=lambda x: x.lx())
        rightmost_rail = self.rails[rail_names[-1][0]]
        self.gnd_x = rightmost_rail + self.m2_width + self.parallel_line_space
        self.width = self.gnd_x + self.rail_height

    def route_clk(self):
        super(cam_control_logic, self).route_clk()
        # clk_buf pin
        self.add_rect("metal2", width=self.m2_width,
                            height=self.clk_buf.get_pin("Z").by()-self.bottom_outputs,
                            offset=vector(self.clk_buf_rail_x, self.bottom_outputs))
        # clock input
        clk_inv_a_pin = self.clk_inv1.get_pin("A")
        y_offset = clk_inv_a_pin.cy() - 0.5*self.m1_width
        x_offset = self.rails["clk"]
        self.add_rect("metal1", offset=vector(clk_inv_a_pin.rx(), y_offset),
                      width=x_offset - clk_inv_a_pin.rx())
        self.add_layout_pin("clk", "metal2", offset=vector(x_offset, y_offset), height=self.height-y_offset)
        self.add_contact(contact.m1m2.layer_stack, offset=vector(x_offset, y_offset))

    def route_se_neg_ff(self):
        # clk
        self.route_ff_clk(self.rails["clk_bar"], self.se_neg_ff)
        # din
        din_pin = self.se_neg_ff.get_pin("din[0]")
        y_offset = din_pin.uy() + self.parallel_line_space

        self.add_rect("metal1", offset=vector(din_pin.lx(), y_offset), width=self.rails["se"] - din_pin.lx())
        self.add_rect("metal2", offset=din_pin.ul(), height=y_offset - din_pin.uy())
        self.add_contact(contact.m1m2.layer_stack,
                         offset=vector(din_pin.lx() + contact.m1m2.second_layer_height, y_offset), rotate=90)
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.rails["se"], y_offset))

        gnd_pin = min(self.se_neg_ff.get_pins("gnd"), key=lambda x: x.by())

        # dout
        y_space = self.line_end_space + contact.m1m2.second_layer_height
        y_offset = min(gnd_pin.by(), self.se_neg_ff.by()) - y_space

        dout_pin = self.se_neg_ff.get_pin("dout_bar[0]")
        offset = vector(dout_pin.lx(), y_offset)
        self.add_rect("metal2", offset=offset, height=dout_pin.by() - offset.y)
        self.add_rect("metal1", offset=offset, width=self.rails["se_neg_ff"]-offset.x)
        self.add_contact(contact.m1m2.layer_stack, offset=offset + vector(contact.m1m2.second_layer_height, 0),
                         rotate=90)
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.rails["se_neg_ff"], y_offset))

        # add seg_nef_ff rail
        latch_tag_pin = self.pre_latch_tags_bar.get_pin("B")
        self.add_rect("metal2", offset=vector(self.rails["se_neg_ff"], latch_tag_pin.by()),
                      height=y_offset - latch_tag_pin.by())


    def route_oeb_csb_web(self):
        self.route_ff_clk(self.rails["clk_buf"], self.oeb_csb_web_inst)

        rail_names = ["oe", "cs", "we"]
        input_pins = ["oeb", "csb", "web"]
        ff_pins = [0, 1, 2]
        y_offset = self.oeb_csb_web_inst.uy()
        for i in range(3):
            y_offset += self.oeb_input_spaces[i]
            rail_x = self.rails[rail_names[i]]
            self.add_input_pin(input_pins[i], rail_x, y_offset)
            self.route_ff_data_in_to_rail(self.oeb_csb_web_inst.get_pin("din[{}]".format(ff_pins[i])), rail_x, y_offset)

        y_offset = self.oeb_csb_web_inst.by()
        via_space = self.m1_width + self.m1_space
        y_spaces = [self.parallel_line_space + self.m1_width, via_space, via_space]
        dest_pins = [self.rblk_bar.get_pin("B"), self.rblk_bar.get_pin("C"),
                     self.mw_we_bar.get_pin("B")]  # lowest pin to connect to
        for i in range(3):
            y_offset -= y_spaces[i]
            rail_x = self.rails[rail_names[i]]
            self.route_ff_data_out_to_rail(self.oeb_csb_web_inst.get_pin("dout_bar[{}]".format(ff_pins[i])),
                                           rail_x, y_offset)
            self.add_rect("metal2", offset=vector(rail_x, dest_pins[i].by()), height=y_offset - dest_pins[i].by())

    def route_seb_mwb_bcast(self):
        self.route_ff_clk(self.rails["clk_buf"], self.seb_mwb_bcast_inst)

        # bcast, mw, se inputs
        input_pins = ["bcastb", "mwb", "seb"]
        rail_names = ["bcast", "mw", "se"]
        ff_pins = [0, 1, 2]
        y_offset = self.seb_mwb_bcast_inst.uy()
        for i in range(3):
            y_offset += self.oeb_input_spaces[i]
            rail_x = self.rails[rail_names[i]]
            self.add_input_pin(input_pins[i], rail_x, y_offset)
            self.route_ff_data_in_to_rail(self.seb_mwb_bcast_inst.get_pin("din[{}]".format(ff_pins[i])),
                                          rail_x, y_offset)

        # bcast, mw, se outputs
        rail_y_offsets = [0] * 6  # offset of top of rail
        via_space = self.m1_width + self.parallel_line_space
        y_spaces = [self.parallel_line_space + self.m1_width] + [via_space] * 2
        y_offset = self.seb_mwb_bcast_inst.by()

        for i in range(2):
            y_offset -= y_spaces[i]
            rail_x = self.rails[rail_names[i]]
            out_pin_name = "dout_bar[{}]".format(i)
            self.route_ff_data_out_to_rail(self.seb_mwb_bcast_inst.get_pin(out_pin_name), rail_x, y_offset)
            rail_y_offsets[i] = y_offset
        # se
        y_offset -= via_space
        dout_bar_pin = self.seb_mwb_bcast_inst.get_pin("dout_bar[2]")
        rail_x = self.rails["se"] + 0.5*self.m2_width
        self.add_path("metal2", [vector(dout_bar_pin.cx(), dout_bar_pin.by() + self.m2_width),
                                 vector(rail_x + 0.5*self.m2_width, dout_bar_pin.by())])
        rail_y_offsets[2] = dout_bar_pin.by()


        # se_bar output
        y_offset -= via_space
        dout_bar_pin = self.seb_mwb_bcast_inst.get_pin("dout[2]")
        rail_x = self.rails["se_bar"] + 0.5*self.m2_width
        self.add_path("metal2", [vector(dout_bar_pin.cx(), dout_bar_pin.by() + self.m2_width),
                                 vector(dout_bar_pin.cx(), y_offset),
                                 vector(rail_x + 0.5*self.m2_width, y_offset)])
        rail_y_offsets[3] = y_offset
        # mw_bar output
        y_offset -= via_space
        dout_bar_pin = self.seb_mwb_bcast_inst.get_pin("dout[1]")
        rail_x = self.rails["mw_bar"] + self.m2_width
        self.add_path("metal2", [vector(dout_bar_pin.cx(), dout_bar_pin.by() + self.m2_width),
                                 vector(rail_x, y_offset),
                                 vector(rail_x, y_offset)])
        rail_y_offsets[4] = y_offset
        # bcast_bar output
        y_offset -= via_space
        dout_bar_pin = self.seb_mwb_bcast_inst.get_pin("dout[0]")
        rail_x = self.rails["bcast_bar"] + self.m2_width
        self.add_path("metal2", [vector(dout_bar_pin.cx(), dout_bar_pin.by() + self.m2_width),
                                 vector(rail_x, y_offset),
                                 vector(rail_x, y_offset)])
        rail_y_offsets[5] = y_offset
        #
        # construct rail to lowest input pin
        rail_names = ["bcast", "mw", "se", "se_bar", "mw_bar", "bcast_bar"]
        lowest_pin = [self.broadcast_buffer.get_pin("in"), self.mw_we_bar.get_pin("A"),
                      self.pre_search_en_bar.get_pin("B"), self.sel_all_banks_bar.get_pin("A"),
                      self.sel_all_banks_bar.get_pin("B"), self.sel_all_banks_bar.get_pin("C")]
        for i in range(6):
            self.add_rect("metal2", offset=vector(self.rails[rail_names[i]], lowest_pin[i].by()),
                          height=rail_y_offsets[i] - lowest_pin[i].by())

    def route_sel_all_banks(self):
        via_x_pos = self.sel_all_banks_bar.rx()
        self.route_pin_to_vertical_rail_m1(self.sel_all_banks_bar.get_pin("A"), self.rails["se_bar"])
        pin = self.sel_all_banks_bar.get_pin("B")
        self.route_pin_to_vertical_rail(pin, self.rails["mw_bar"],
                                        via_x_pos, "center", rail_via_y=pin.uy() - 0.5*contact.m1m2.second_layer_height)
        self.route_pin_to_vertical_rail(self.sel_all_banks_bar.get_pin("C"), self.rails["bcast_bar"],
                                        via_x_pos, "center")

        self.route_output_to_buffer(self.sel_all_banks_bar.get_pin("Z"), self.sel_all_banks_buffer)
        self.route_buffer_output(self.sel_all_banks_buffer, "sel_all_banks")

    def route_sel_all_rows(self):
        # connect in pin
        in_pin = self.broadcast_buffer.get_pin("in")
        y_offset = in_pin.cy() - 0.5*self.m2_width
        via_x = self.broadcast_buffer.rx() + self.line_end_space + contact.m1m2.second_layer_height
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.rails["bcast"], y_offset))
        self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x, y_offset), rotate=90)
        self.add_rect("metal1", offset=vector(via_x, y_offset), width=self.rails["bcast"] - via_x)
        self.add_rect("metal2", offset=vector(in_pin.rx(), y_offset), width=via_x - in_pin.rx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(in_pin.rx(), y_offset), rotate=90)
        # connect out pin
        out_pin = self.broadcast_buffer.get_pin("out")
        y_offset = out_pin.by()
        x_offset = self.rails["sel_all_rows"]
        self.add_rect("metal1", offset=vector(out_pin.lx(), y_offset), width=x_offset - out_pin.lx())
        self.add_contact(contact.m1m2.layer_stack,
                         offset=vector(x_offset, out_pin.by() + self.m2_width - contact.m1m2.second_layer_height))
        self.add_rect("metal2", offset=vector(x_offset, self.bottom_outputs),
                            height=y_offset - self.bottom_outputs)

    def route_clk_bar_cs(self):
        # connect inputs
        via_x_pos = self.clk_bar_cs_bar.rx()
        self.route_pin_to_vertical_rail_m1(self.clk_bar_cs_bar.get_pin("A"), self.rails["cs"])
        self.route_pin_to_vertical_rail(self.clk_bar_cs_bar.get_pin("B"), self.rails["clk_bar"], via_x_pos, "center")

        # nand output to inverter
        a_pin = self.clk_bar_cs.get_pin("A")
        self.add_rect("metal1", offset=vector(a_pin.rx(), a_pin.cy() - 0.5*self.m1_width),
                      width=self.clk_bar_cs_bar.get_pin("Z").lx() - a_pin.rx())

        # inverter output to rail
        rail_x = self.rails["clk_bar_cs"]
        rail_top = self.clk_bar_cs.by() - 0.5*self.rail_height - self.parallel_line_space
        out_pin = self.clk_bar_cs.get_pin("Z")

        via_x_pos = self.mw_buffer.rx() + self.line_end_space
        self.add_path("metal2", [
            out_pin.bc(),
            vector(out_pin.cx(), self.clk_bar_cs.by()),
            vector(via_x_pos + 0.5*self.m1_width, self.clk_bar_cs.by()),
            vector(via_x_pos + 0.5*self.m1_width, rail_top)
        ])

        self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x_pos + contact.m1m2.second_layer_height,
                                                                 rail_top - contact.m1m2.second_layer_width),
                         rotate=90)
        self.add_rect("metal1", offset=vector(via_x_pos, rail_top - self.m1_width), width=rail_x - via_x_pos)
        self.add_contact(contact.m1m2.layer_stack, offset=vector(rail_x, rail_top - contact.m1m2.second_layer_height))

        # add rail
        rail_bottom = self.pre_w_en_bar.get_pin("B").cy()
        self.add_rect("metal2", offset=vector(rail_x, rail_bottom), height=rail_top - rail_bottom)

    def route_mw_en(self):
        # connect in pin
        in_pin = self.mw_buffer.get_pin("in")
        y_offset = in_pin.cy() - 0.5 * self.m2_width
        via_x = self.mw_buffer.rx() + self.line_end_space + contact.m1m2.second_layer_height
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.rails["mw"], y_offset))
        self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x, y_offset), rotate=90)
        self.add_rect("metal1", offset=vector(via_x, y_offset), width=self.rails["mw"] - via_x)
        self.add_rect("metal2", offset=vector(in_pin.rx(), y_offset), width=via_x - in_pin.rx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(in_pin.rx(), y_offset), rotate=90)
        # connect out pin
        out_pin = self.mw_buffer.get_pin("out")
        y_offset = out_pin.by()
        x_offset = self.rails["mw_en"]
        self.add_rect("metal1", offset=vector(out_pin.lx(), y_offset), width=x_offset - out_pin.lx())
        self.add_contact(contact.m1m2.layer_stack,
                         offset=vector(x_offset, out_pin.by() + self.m2_width - contact.m1m2.second_layer_height))
        self.add_rect("metal2", offset=vector(x_offset, self.bottom_outputs),
                            height=y_offset - self.bottom_outputs)

    def route_latch_tags(self):
        via_x_pos = self.clk_bar_cs_bar.rx()
        self.route_pin_to_vertical_rail(self.pre_latch_tags_bar.get_pin("B"), self.rails["se_neg_ff"],
                                        via_x_pos, "center")
        self.route_pin_to_vertical_rail_m1(self.pre_latch_tags_bar.get_pin("A"), self.rails["clk_buf"])
        a_pin = self.pre_latch_tags.get_pin("A")
        self.add_rect("metal1", offset=vector(a_pin.rx(), a_pin.cy() - 0.5*self.m1_width),
                      width=self.pre_latch_tags_bar.get_pin("Z").lx() - a_pin.rx())
        self.route_output_to_buffer(self.pre_latch_tags.get_pin("Z"), self.latch_tags_buffer)
        self.route_buffer_output(self.latch_tags_buffer, "latch_tags")

    def route_matchline_chb(self):
        via_x_pos = self.pre_ml_chb.rx()
        self.route_pin_to_vertical_rail(self.pre_ml_chb.get_pin("B"), self.rails["clk_buf"],
                                        via_x_pos, "center")
        self.route_pin_to_vertical_rail_m1(self.pre_ml_chb.get_pin("A"), self.rails["se"])
        self.route_output_to_buffer(self.pre_ml_chb.get_pin("Z"), self.ml_chb_buffer)
        self.route_buffer_output(self.ml_chb_buffer, "matchline_chb")

    def route_search_en(self):
        via_x_pos = self.pre_search_en_bar.rx()
        self.route_pin_to_vertical_rail(self.pre_search_en_bar.get_pin("B"), self.rails["se"],
                                        via_x_pos, "center")
        self.route_pin_to_vertical_rail_m1(self.pre_search_en_bar.get_pin("A"), self.rails["clk_bar_cs"])
        a_pin = self.pre_search_en.get_pin("A")
        self.add_rect("metal1", offset=vector(a_pin.rx(), a_pin.cy() - 0.5*self.m1_width),
                      width=self.pre_search_en_bar.get_pin("Z").lx() - a_pin.rx())
        self.route_output_to_buffer(self.pre_search_en.get_pin("Z"), self.search_en_buffer)
        self.route_buffer_output(self.search_en_buffer, "search_en")

    def route_w_en(self):
        via_x_pos = self.mw_we_bar.rx()
        self.route_pin_to_vertical_rail(self.mw_we_bar.get_pin("B"), self.rails["we"],
                                        via_x_pos, "center")
        self.route_pin_to_vertical_rail_m1(self.mw_we_bar.get_pin("A"), self.rails["mw"])
        a_pin = self.mw_we.get_pin("A")
        self.add_rect("metal1", offset=vector(a_pin.rx(), a_pin.cy() - 0.5 * self.m1_width),
                      width=self.mw_we_bar.get_pin("Z").lx() - a_pin.rx())
        # mw_we to pre_w_en_bar
        via_x_pos = self.pre_w_en_bar.rx()
        a_pin = self.pre_w_en_bar.get_pin("A")
        z_pin = self.mw_we.get_pin("Z")
        self.add_path("metal2", [
            z_pin.bc(),
            vector(z_pin.cx(), self.mw_we.by()),
            vector(via_x_pos, self.mw_we.by()),
            vector(via_x_pos, a_pin.cy())
        ])
        self.route_pin_to_vertical_rail_m1(a_pin, via_x_pos - 0.5*self.m2_width)
        # clk_bar_cs input to pre_w_en_bar
        self.route_pin_to_vertical_rail(self.pre_w_en_bar.get_pin("B"), self.rails["clk_bar_cs"],
                                        via_x_pos, "center")
        # pre_w_en_bar to pre_w_en
        a_pin = self.pre_w_en.get_pin("A")
        self.add_rect("metal1", offset=vector(a_pin.rx(), a_pin.cy() - 0.5 * self.m1_width),
                      width=self.pre_w_en_bar.get_pin("Z").lx() - a_pin.rx())
        # buffer
        self.route_output_to_buffer(self.pre_w_en.get_pin("Z"), self.w_en_buffer)
        self.route_buffer_output(self.w_en_buffer, "w_en")

    def route_blk(self):
        super(cam_control_logic, self).route_blk()
        self.add_rect("metal2", offset=vector(self.rails["s_en"], self.bottom_outputs),
                            height=self.s_en.get_pin("Z").uy() - self.bottom_outputs)

    def route_power(self):
        # extend left vdd to top
        self.vdd_rect = self.add_layout_pin("vdd", "metal1", offset=vector(self.left_vdd.lx(), 0),
                                      width=self.rail_height, height=self.height)

        self.connect_rbl_right_vdd()

        # create rail to the right
        rbl_buffer_gnd = self.s_en.get_pin("gnd")
        self.gnd_rail = self.add_layout_pin("gnd", "metal1", width=self.rail_height, height=self.height,
                                      offset=vector(self.gnd_x, 0))
        # connect rbl ground to gnd rail
        rbl_gnd = self.rbl.get_pin("gnd")
        self.add_rect("metal1", width=self.rail_height, height=rbl_buffer_gnd.by() - rbl_gnd.uy(),
                      offset=rbl_gnd.ul())

        for cell in [self.rblk, self.s_en, self.w_en_buffer, self.mw_we,
                     self.pre_search_en, self.ml_chb_buffer, self.latch_tags_buffer, self.mw_buffer,
                     self.clk_bar_cs_bar, self.broadcast_buffer, self.sel_all_banks_bar,
                     self.seb_mwb_bcast_inst, self.oeb_csb_web_inst,
                     self.se_neg_ff, self.clk_bar, self.clk_inv1, self.clk_buf]:
            for vdd_pin in cell.get_pins("vdd"):
                self.pin_to_vdd(vdd_pin, self.vdd_rect)

            for gnd_pin in cell.get_pins("gnd"):
                self.pin_to_gnd(gnd_pin, self.gnd_rail)


    # helpers

    def add_input_pin(self, rail_name, rail_x, y_offset):
        self.add_layout_pin(rail_name, "metal2", offset=vector(rail_x, y_offset), height=self.height-y_offset)

    def route_ff_clk(self, rail, instance):
        clk_pin = instance.get_pin("clk")
        self.add_rect("metal1", offset=clk_pin.lr(), width=rail - clk_pin.rx(), height=clk_pin.height())
        self.add_contact(contact.m1m2.layer_stack,
                         offset=vector(rail, clk_pin.cy() - 0.5*contact.m1m2.second_layer_height))

    def route_ff_data_in_to_rail(self, pin, rail_x, y_offset):
        self.add_contact_center(contact.m1m2.layer_stack,
                                offset=vector(pin.cx(), y_offset + 0.5*contact.m1m2.second_layer_width), rotate=90)
        rect_width = max(self.metal1_minwidth_fill, rail_x - pin.lx())
        self.add_rect("metal1", vector(rail_x - rect_width, y_offset), width=rect_width)
        self.add_rect("metal2", offset=pin.ul(), height=y_offset - pin.uy())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(rail_x, y_offset))

    def route_ff_data_out_to_rail(self, pin, rail_x, y_offset):
        self.add_contact(contact.m1m2.layer_stack,
                                offset=vector(pin.rx() - contact.m1m2.second_layer_width, y_offset), rotate=90)
        rect_width = max(self.metal1_minwidth_fill, rail_x - pin.lx())
        self.add_rect("metal1", vector(rail_x - rect_width, y_offset), width=rect_width)
        self.add_rect("metal2", offset=vector(pin.lx(), y_offset), height=pin.by() - y_offset)
        self.add_contact(contact.m1m2.layer_stack,
                         offset=vector(rail_x, y_offset + self.m1_width - contact.m1m2.second_layer_height))


    def route_buffer_output(self, buffer_instance, rail_name):

        out_pin = buffer_instance.get_pin("out")
        self.add_rect("metal1", offset=out_pin.rc(), width=self.rails[rail_name] - out_pin.rx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.rails[rail_name], out_pin.cy()
                                                                 - 0.5*contact.m1m2.second_layer_height))
        self.add_rect("metal2", offset=vector(self.rails[rail_name], self.bottom_outputs),
                      height=out_pin.cy()-self.bottom_outputs)

    def route_pin_to_vertical_rail_m1(self, pin, rail_x):
        self.add_contact_center(layers=self.m1m2_layers, offset=vector(rail_x + 0.5*contact.m1m2.second_layer_width,
                                                                       pin.cy()))
        self.add_rect("metal1", offset=vector(pin.rx(), pin.cy() - 0.5*self.m1_width), width=rail_x - pin.rx())
