import cam_bank
import contact
import debug
import re
import sram
import utils
from vector import vector


class Cam(sram.sram):

    def compute_sizes(self):
        super(Cam, self).compute_sizes()
        self.control_size = len(self.get_control_logic_names())
        if self.words_per_row > 1:
            debug.error("Only one word per row permitted for CAM", -1)

    def get_precharge_vdd_to_top(self):
        precharge_vdd = utils.get_pin_rect(self.bank.block_insts[0].mod.precharge_array_inst.get_pin("vdd"),
                                           [self.bank.block_insts[0]])
        return self.bank.height - precharge_vdd[1][1], precharge_vdd[1][1] - precharge_vdd[0][1]

    def get_control_logic_names(self):
        return ["clk_buf", "s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows", "latch_tags",
                "matchline_chb"]

    def add_single_bank_pins(self):
        for i in range(self.word_size):
            self.copy_layout_pin(self.bank_inst, "DATA[{}]".format(i))
            self.copy_layout_pin(self.bank_inst, "MASK[{}]".format(i))

        for i in range(self.addr_size):
            self.copy_layout_pin(self.bank_inst, "ADDR[{}]".format(i))

        self.add_control_logic_pins()

    def add_control_logic_pins(self):
        for (old, new) in zip(["csb", "web", "oeb", "seb", "mwb", "bcastb", "clk"],
                             ["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"]):
            self.copy_layout_pin(self.control_logic_inst, old, new)

    def route_control_logic_to_left_bank(self, bank_inst):
        control_logic_names = self.get_control_logic_names()
        for i in range(len(control_logic_names)):
            ctrl_pin = self.control_logic_inst.get_pin(control_logic_names[i])
            bank_pin = bank_inst.get_pin(control_logic_names[i])

            self.add_rect("metal3", offset=ctrl_pin.ul(), height=bank_pin.uy() - ctrl_pin.uy())
            self.add_rect("metal2", offset=bank_pin.lr(), width=ctrl_pin.rx() - bank_pin.rx())
            if control_logic_names[i] in ["sel_all_banks", "clk_buf", "sel_all_rows"]:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(ctrl_pin.lx(), bank_pin.by()))
            else:
                self.add_contact(contact.m2m3.layer_stack, offset=vector(ctrl_pin.rx(), bank_pin.by()), rotate=90)

    def route_single_bank(self):
        self.route_control_logic_to_left_bank(self.bank_inst)

        # route bank_sel to vdd
        bank_sel_pin = self.bank_inst.get_pin("bank_sel")
        self.add_rect("metal1", offset=bank_sel_pin.ll(), width=self.bank_inst.rx() - bank_sel_pin.lx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.bank_inst.rx(), bank_sel_pin.by()),
                         size=[1, 2], rotate=90)

        self.route_one_bank_power()

    def route_two_banks(self):
        self.route_shared_banks()

        # connect address pins
        self.connect_lower_address_pins()


        self.route_two_bank_logic()

        self.route_single_msb_address()

        self.route_two_banks_power()

    def route_four_banks(self):
        self.route_shared_banks()

        # connect address pins
        self.connect_lower_address_pins()
        bank_indices = [(0, 2), (1, 3)]
        for j in [0, 1]:
            top_bank = self.bank_inst[bank_indices[j][1]]
            bottom_bank = self.bank_inst[bank_indices[j][0]]

            # address pins
            for i in range(self.bank_addr_size):
                pin_name = "ADDR[{}]".format(i)
                top_pin = top_bank.get_pin(pin_name)
                bottom_pin = bottom_bank.get_pin(pin_name)
                self.add_rect("metal3", offset=bottom_pin.ul(), width=top_pin.width(),
                              height=top_pin.by() - bottom_pin.uy())
                via_y = top_pin.by() - (i % 2) * contact.m2m3.second_layer_height
                self.add_contact(contact.m2m3.layer_stack, offset=vector(top_pin.lx(), via_y))

        self.route_four_bank_logic()
        self.route_double_msb_address()

        self.route_four_banks_power()

    def connect_lower_address_pins(self):
        min_bus_y = min(self.data_bus_positions.values(), key=lambda x: x[1])[1]
        base_y = min_bus_y - self.bank_addr_size * self.m4_pitch - self.wide_m1_space
        for i in range(self.bank_addr_size):
            addr_name = "ADDR[{}]".format(i)
            left_pin = self.bank_inst[0].get_pin(addr_name)
            right_pin = self.bank_inst[1].get_pin(addr_name)
            rail_y = base_y + (self.bank_addr_size - i) * self.m4_pitch
            for pin in [left_pin, right_pin]:
                self.add_rect("metal3", offset=vector(pin.lx(), rail_y), height=min_bus_y-rail_y)
                self.add_rect("metal2", offset=pin.ul(), height=rail_y - pin.uy())
                self.add_contact(contact.m2m3.layer_stack, offset=(pin.lx(), rail_y - contact.m2m3.second_layer_height))
                self.add_contact(contact.m3m4.layer_stack, offset=(pin.lx(), rail_y - contact.m3m4.second_layer_height))

            self.add_layout_pin(addr_name, layer="metal4", offset=vector(left_pin.lx(), rail_y - self.m4_width),
                                width=right_pin.rx() - left_pin.lx())




    def create_modules(self):
        """ Create all the modules that will be used """

        # Create the control logic module
        self.control_logic = self.mod_control_logic(num_rows=self.num_rows)
        self.add_mod(self.control_logic)

        # Create the bank module (up to four are instantiated)
        self.bank = cam_bank.CamBank(word_size=self.word_size,
                         num_words=self.num_words_per_bank,
                         words_per_row=self.words_per_row,
                         name="bank")
        self.add_mod(self.bank)

        # Conditionally create the
        if self.num_banks > 1:
            self.create_multi_bank_modules()

        self.bank_count = 0

        self.power_rail_width = self.bank.cam_block.vdd_rail_width
        # Leave some extra space for the pitch
        self.power_rail_pitch = self.bank.cam_block.vdd_rail_width + self.wide_m1_space


    def add_pins(self):
        """ Add pins for entire CAM. """
        # These are used to create the physical pins too
        self.control_logic_inputs = ["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"]
        self.control_logic_outputs = ["s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows",
                                      "latch_tags", "matchline_chb", "clk_buf"]

        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i), "INOUT")
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i), "INPUT")
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i), "INPUT")

        self.add_pin_list(["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"], "INPUT")
        self.add_pin("vdd", "POWER")
        self.add_pin("gnd", "GROUND")

    def add_control_logic(self, position, rotate=0, mirror="R0"):
        """ Add and place control logic """
        self.control_logic_inst = self.add_inst(name="control",
                                              mod=self.control_logic,
                                              offset=position + vector(0, self.control_logic.height),
                                              mirror="MX",
                                              rotate=rotate)
        self.connect_inst(["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"] +
                          ["clk_buf", "s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows",
                           "latch_tags", "matchline_chb"] +
                          ["vdd", "gnd"])

    def compute_two_bank_logic_locs(self):


        # Control is placed below the bank control signals
        # align control_logic vdd with first bank's vdd
        bank_inst = self.bank_inst[0]
        control_pins = map(bank_inst.get_pin, self.control_logic_outputs + ["bank_sel"])
        self.bottom_control_pin = min(control_pins, key=lambda x: x.by())
        self.top_control_pin = max(control_pins, key=lambda x: x.uy())

        control_logic_pins = map(self.control_logic.get_pin, self.control_logic_outputs)
        right_control_pin = max(control_logic_pins, key=lambda x: x.rx())

        control_gap = 2*self.wide_m1_space + self.implant_space
        control_logic_x = bank_inst.rx() + self.bank_to_bus_distance

        msb_address_x = control_logic_x + right_control_pin.rx() + self.wide_m1_space

        self.msb_address_position = vector(msb_address_x,
                                           self.bottom_control_pin.by() - self.wide_m1_space - self.msb_address.height)


        self.control_logic_position = vector(control_logic_x, self.msb_address_position.y - control_gap - self.control_logic.height)

    def add_two_bank_logic(self):
        """ Add the control and MSB logic """

        self.add_control_logic(position=self.control_logic_position)

        self.msb_address_inst = self.add_inst(name="msb_address",
                                              mod=self.msb_address,
                                              offset=self.msb_address_position+vector(self.msb_address.width,
                                                                                      0),
                                              mirror="MY",
                                              rotate=0)
        self.msb_bank_sel_addr = "ADDR[{}]".format(self.addr_size-1)
        self.connect_inst([self.msb_bank_sel_addr,"bank_sel[1]","bank_sel[0]","clk_buf", "vdd", "gnd"])

    def route_two_bank_logic(self):
        self.route_control_logic_to_left_bank(self.bank_inst[0])
        control_pin_names = self.get_control_logic_names()
        for i in range(len(control_pin_names)):
            pin_name = control_pin_names[i]
            # connect bank input from right to left
            left_pin = self.bank_inst[0].get_pin(pin_name)
            right_pin = self.bank_inst[1].get_pin(pin_name)
            self.add_rect(left_pin.layer, offset=left_pin.lr(), width=right_pin.lx() - left_pin.rx())

    def route_single_msb_address(self):
        """ Route one MSB address bit for 2-bank SRAM """

        # connect bank sel pins
        pin_names = ["dout_bar[0]", "dout[0]"]
        for i in range(2):
            pin_name = pin_names[i]
            pin = self.msb_address_inst.get_pin(pin_name)
            bank_sel_pin = self.bank_inst[i].get_pin("bank_sel")

            if i == 0:
                pin_x = bank_sel_pin.rx()
            else:
                pin_x = bank_sel_pin.lx()

            self.add_path("metal2", [pin.uc(), vector(pin.cx(), bank_sel_pin.cy()), vector(pin_x, bank_sel_pin.cy())])


        # Connect clk
        ff_clk_pin = self.msb_address_inst.get_pin("clk")
        ctrl_clk_pin = self.control_logic_inst.get_pin("clk_buf")
        self.add_rect("metal1", offset=vector(ctrl_clk_pin.lx(), ff_clk_pin.by()),
                      width=ff_clk_pin.rx() - ctrl_clk_pin.lx(), height=ff_clk_pin.height())
        via_offset = vector(ctrl_clk_pin.lx(), ff_clk_pin.cy() - 0.5*contact.m1m2.second_layer_height)
        self.add_contact(contact.m1m2.layer_stack, offset=via_offset)
        self.add_contact(contact.m2m3.layer_stack, offset=via_offset)
        self.add_rect("metal2", offset=via_offset, height=self.metal1_minwidth_fill)

        self.copy_layout_pin(self.msb_address_inst, "din[0]", "ADDR[{}]".format(self.addr_size-1))

    def compute_four_bank_logic_locs(self):

        self.compute_two_bank_logic_locs()

        predecoder_space = 2*self.wide_m1_space + self.implant_space
        predecoder_x = self.bank_inst[0].rx() + self.bank_to_bus_distance

        predecoder_y = self.msb_address_position.y + self.msb_address.height - self.msb_decoder.height
        msb_address_y = predecoder_y - predecoder_space - self.msb_address.height
        control_bus_y = msb_address_y - (self.msb_address_position.y - self.control_logic_position.y)


        self.msb_decoder_position = vector(predecoder_x, predecoder_y)
        self.msb_address_position.y = msb_address_y
        self.control_logic_position.y = control_bus_y

        # address bus is to the left of bank_sel
        self.bank_sel_x = self.bank_sel_x + self.msb_address_position.x
        self.addr_bus_x = self.bank_sel_x - self.m2_pitch * self.bank_addr_size
        self.control_bus_x = self.bank_sel_x + self.m2_pitch * self.num_banks

    def get_msb_address_locations(self):
        return self.msb_address_position, "R0"

    def route_four_bank_logic(self):
        self.vert_control_bus_positions = {}
        rail_pitch = contact.m2m3.second_layer_height + self.line_end_space
        control_logic_names = self.get_control_logic_names()
        control_logic_pins = sorted(map(self.control_logic_inst.get_pin, control_logic_names), key=lambda x: x.rx())
        control_top = self.control_logic_inst.uy()
        base_x = control_logic_pins[0].lx()
        for i in range(len(control_logic_names)):
            pin = control_logic_pins[i]
            bend_y = control_top + (len(control_logic_names) - i) * self.m3_pitch
            x_offset = base_x + i * rail_pitch
            self.vert_control_bus_positions[pin.name] = x_offset
            # extend m3 to top of control logic module
            self.add_rect("metal3", offset=pin.ul(), height=bend_y - pin.uy(), width=pin.width())


            self.add_rect("metal3", offset=vector(pin.lx(), bend_y), width=x_offset - pin.lx() + self.m3_width)

            # extend rail to top bank
            top_pin = self.bank_inst[2].get_pin(pin.name)
            bot_pin = self.bank_inst[0].get_pin(pin.name)
            bot_right_pin = self.bank_inst[1].get_pin(pin.name)
            top_right_pin = self.bank_inst[3].get_pin(pin.name)
            self.add_rect("metal3", offset=vector(x_offset, bend_y), height=top_pin.uy() - bend_y)
            # connect horizontally
            for (left, right) in [(top_pin, top_right_pin), (bot_pin, bot_right_pin)]:
                self.add_rect(left.layer, offset=left.lr(), width=right.lx() - left.rx())
            # add m2->m3 via at bank pin height
            for bank_pin in [top_pin, bot_pin]:
                self.add_contact(contact.m2m3.layer_stack, offset=vector(x_offset + self.m3_width, bank_pin.by()),
                                 rotate=90)


    def route_double_msb_address(self):
        # add address pins
        self.copy_layout_pin(self.msb_address_inst, "din[0]", "ADDR[{}]".format(self.addr_size - 2))
        self.copy_layout_pin(self.msb_address_inst, "din[1]", "ADDR[{}]".format(self.addr_size - 1))

        rail_separation = contact.m2m3.first_layer_height + self.m3_space
        # connect dout[0]
        decoder_pin = self.msb_decoder_inst.get_pin("in[0]")
        msb_pin = self.msb_address_inst.get_pin("dout[0]")
        self.add_path("metal2", [
            msb_pin.uc() - vector(0, 0.5*self.m2_width),
            vector(decoder_pin.cx(), msb_pin.uy() - 0.5*self.m2_width),
            vector(decoder_pin.cx(), decoder_pin.by())
        ])
        # connect dout[1]
        decoder_pin = self.msb_decoder_inst.get_pin("in[1]")
        msb_pin = self.msb_address_inst.get_pin("dout[1]")
        self.add_path("metal2", [
            msb_pin.uc() - vector(0, 0.5 * self.m2_width),
            msb_pin.uc() - vector(0, 0.5 * self.m2_width + rail_separation),
            vector(decoder_pin.cx(), msb_pin.uy() - 0.5 * self.m2_width + rail_separation),
            vector(decoder_pin.cx(), decoder_pin.by())
        ])

        # Connect clk
        clk_pin = self.msb_address_inst.get_pin("clk")
        clk_pos = clk_pin.lr()
        rail_pos = self.vert_control_bus_positions["clk_buf"]

        self.add_contact(contact.m1m2.layer_stack, offset=clk_pos, rotate=90)
        via_y = self.msb_address_inst.by() - contact.m2m3.second_layer_height - self.m2_width
        self.add_path("metal2", [
            vector(clk_pin.rx() - 0.5*self.m2_width, clk_pin.by()),
            vector(clk_pin.rx() - 0.5*self.m2_width, via_y),
            vector(rail_pos, via_y)
        ])
        self.add_contact(contact.m2m3.layer_stack,
                         offset=vector(rail_pos, via_y))
        self.add_rect("metal3", offset=vector(rail_pos, via_y), height=self.msb_address_inst.uy() - via_y)

        # Connect bank decoder outputs to the bank select vertical bus wires

        for i in range(self.num_banks):
            msb_pin = self.msb_decoder_inst.get_pin("out[{}]".format(i))

            rail_x = self.msb_decoder_inst.rx() + self.m3_space + (i + 1) * self.m3_pitch
            self.add_rect("metal2", offset=msb_pin.ur(), width=rail_x - msb_pin.rx())
            self.add_contact(contact.m2m3.layer_stack, offset=vector(rail_x, msb_pin.uy()))

            # m3 to bank sel
            bank_sel_pin = self.bank_inst[i].get_pin("bank_sel")
            self.add_rect("metal3", offset=vector(rail_x, msb_pin.uy()), height=bank_sel_pin.uy() - msb_pin.uy())

            self.add_path("metal2", [
                vector(bank_sel_pin.rx(), bank_sel_pin.cy()),
                vector(rail_x + (i - 1 % 2) * self.m2_width, bank_sel_pin.cy())
            ])

            if i == 0:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(rail_x + self.m3_width, bank_sel_pin.by()), rotate=90)
                fill_y = bank_sel_pin.uy() - contact.m2m3.second_layer_height  # prevent line end spacing rule
                self.add_rect("metal2", offset=vector(rail_x, fill_y), height=bank_sel_pin.uy() - fill_y)
            elif i == 1:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(rail_x, bank_sel_pin.uy() - contact.m1m2.second_layer_height))
            else:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(rail_x + self.m3_width + (i % 2) * contact.m2m3.second_layer_height,
                                               bank_sel_pin.by()), rotate=90)

    def connect_address_decoder_control_gnd(self):
        control_gnd = self.control_logic_inst.get_pin("gnd")

        # connect msb_address, decoder and control_logic gnd pins
        gnd_pins = self.msb_address_inst.get_pins("gnd") + self.msb_decoder_inst.get_pins("gnd")
        gnd_pins = filter(lambda x: x.layer == "metal1", gnd_pins)
        top_gnd = max(gnd_pins, key=lambda x: x.by())
        for gnd_pin in gnd_pins:
            self.add_rect("metal1", height=gnd_pin.height(),
                          width=control_gnd.rx() - gnd_pin.rx(),
                          offset=gnd_pin.lr())



        self.add_rect("metal1", offset=control_gnd.ul(), width=control_gnd.width(),
                      height=top_gnd.uy() - control_gnd.uy())



    def add_horizontal_busses(self):
        """ Add the horizontal and vertical busses """
        super(Cam, self).add_horizontal_busses()
        # Horizontal data bus
        self.mask_bus_names = ["MASK[{}]".format(i) for i in range(self.word_size)]
        self.mask_bus_positions = self.create_bus(layer="metal4",
                                                  pitch=self.m4_pitch,
                                                  offset=(self.data_bus_offset +
                                                          vector(0, self.m4_width + 0.5*(self.m4_pitch - 2*self.m4_width))),
                                                  names=self.mask_bus_names,
                                                  length=self.data_bus_width,
                                                  vertical=False,
                                                  make_pins=True)

    def route_shared_banks(self):
        super(Cam, self).route_shared_banks()
        self.route_data_bus(self.mask_bus_names, self.mask_bus_positions, contact.m3m4.layer_stack)


    def connect_inst(self, args, check=True):
        if self.insts[-1].name.startswith("bank"):
            args = []
            for i in range(self.word_size):
                args.append("DATA[{0}]".format(i))
            for i in range(self.word_size):
                args.append("MASK[{0}]".format(i))
            for i in range(self.bank_addr_size):
                args.append("ADDR[{0}]".format(i))
            args.append("sel_all_banks")
            if self.num_banks > 1:
                bank_name = self.insts[-1].name
                bank_num = re.match(".*bank(?P<bank_num>\d+)", bank_name).group('bank_num')
                args.append("bank_sel[{0}]".format(bank_num))
            else:
                args.append("vdd")
            args.extend(["clk_buf", "s_en", "w_en", "search_en", "matchline_chb", "mw_en", "sel_all_rows", "latch_tags",
                         "vdd", "gnd"])
        super(Cam, self).connect_inst(args, check)
