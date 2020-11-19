from base.contact import m1m2, cross_m2m3, m2m3, m3m4
from base.design import METAL2, METAL3, METAL1, METAL4
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.push_rules.horizontal_bank import HorizontalBank
from modules.shared_decoder.cmos_sram import CmosSram


class HorizontalSram(CmosSram):
    rotation_for_drc = GDS_ROT_270
    config_template = "config_push_hs_{}"

    def add_pins(self):
        for j in range(self.num_banks):
            for i in range(self.word_size):
                self.add_pin("DATA_{0}[{1}]".format(j + 1, i))
                self.add_pin("MASK_{0}[{1}]".format(j + 1, i))
        for i in range(self.bank_addr_size):
            self.add_pin("ADDR[{0}]".format(i))
        self.add_pin_list(["read", "clk", "bank_sel", "sense_trig",
                           "vdd", "gnd", "precharge_trig"])

    def route_layout(self):
        super().route_layout()
        self.route_decoder_enable()
        self.route_power_grid()

    def create_bank(self):
        self.bank = HorizontalBank(name="bank", word_size=self.word_size,
                                   num_words=self.num_words_per_bank,
                                   words_per_row=self.words_per_row, num_banks=self.num_banks)
        self.add_mod(self.bank)
        # self.left_bank = HorizontalBank(name="left_bank", word_size=self.word_sizer,
        #                                 num_words=self.num_words_per_bank,
        #                                 words_per_row=self.words_per_row, num_banks=self.num_banks,
        #                                 is_left_bank=True)
        # self.add_mod(self.left_bank)

    def get_bank_connections(self, bank_num):
        connections = super().get_bank_connections(0)
        bank_sel_index = connections.index("bank_sel")
        other_connections = ["bank_sel", "read", "clk", "sense_trig", "precharge_trig"]
        if bank_num == 0:
            other_connections.extend(["clk_buf_1", "clk_bar_1", "vdd", "gnd", "wordline_en"])
        else:
            other_connections.extend(["clk_buf_2", "clk_bar_2", "vdd", "gnd"])
        return connections[:bank_sel_index] + other_connections

    def get_row_decoder_connections(self):
        connections = super().get_row_decoder_connections() + ["wordline_en"]
        return connections

    def add_row_decoder(self):

        left_most_rail_x = self.bank.leftmost_rail.offset.x
        max_predecoder_x = (left_most_rail_x - self.get_wide_space(METAL2) -
                            self.row_decoder.width)
        max_row_decoder_x = self.bank.wordline_driver_inst.lx() - self.row_decoder.row_decoder_width
        x_offset = min(max_predecoder_x, max_row_decoder_x)
        y_offset = (self.bank.bitcell_array_inst.uy() - self.row_decoder.height
                    - self.bank.bitcell.height)
        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.row_decoder,
                                              offset=vector(x_offset, y_offset))

        self.connect_inst(self.get_row_decoder_connections())

    def route_row_decoder_clk(self):
        clk_rail = getattr(self.bank, "clk_buf_rail")

        decoder_clk_pins = self.row_decoder_inst.get_pins("clk")
        valid_decoder_pins = list(filter(lambda x: x.by() > clk_rail.by(), decoder_clk_pins))
        closest_clk = min(valid_decoder_pins, key=lambda x: abs(clk_rail.by() - x.by()))

        top_mask_clock = max(self.bank.mask_in_flops_inst.get_pins("clk"), key=lambda x: x.cy())

        predecoder_mod = (self.row_decoder.pre2x4_inst + self.row_decoder.pre3x8_inst)[0]
        predecoder_vdd_height = predecoder_mod.get_pins("vdd")[0].height()
        wide_space = self.get_wide_space(METAL3)

        y_offset = closest_clk.by() + 0.5 * predecoder_vdd_height + wide_space

        if y_offset > top_mask_clock.by():
            y_offset = max(y_offset, top_mask_clock.cy() + wide_space)
            self.add_rect(METAL2, offset=clk_rail.ul(), width=clk_rail.width,
                          height=y_offset + m1m2.height - clk_rail.uy())
        via_y = y_offset + 0.5 * m1m2.height
        self.add_contact_center(m1m2.layer_stack, offset=vector(clk_rail.cx(), via_y))
        m1_y = y_offset + 0.5 * m1m2.height - 0.5 * self.m1_width
        self.add_rect(METAL1, offset=vector(closest_clk.lx(), m1_y),
                      width=clk_rail.cx() - closest_clk.lx())
        self.add_contact_center(m1m2.layer_stack, offset=vector(closest_clk.cx(), via_y))

    def join_decoder_wells(self):
        pass

    def route_decoder_power(self):
        # connect wordline driver gnd to decoder gnd
        for pin in self.bank.wordline_driver_inst.get_pins("gnd"):
            self.add_contact_center(m2m3.layer_stack,
                                    offset=vector(pin.lx() + 0.5 * m2m3.height, pin.cy()),
                                    rotate=90)
        # connect decoder tap vdd to bank mid vdd
        decoder_tap_vdd = getattr(self.row_decoder, "tap_vdd_pins")[0]
        decoder_tap_bottom = self.row_decoder.decoder_and_tap.height - decoder_tap_vdd.rx()
        vdd_difference = (decoder_tap_bottom
                          - self.bank.bitcell_array.body_tap.get_pin("vdd").by())
        for pin in self.row_decoder_inst.get_pins("vdd"):
            if not pin.layer == METAL3 or pin.uy() <= self.bank.wordline_driver_inst.by():
                continue
            x_offset = pin.rx() + pin.height() + self.get_wide_space(METAL3)
            self.add_rect(METAL3, offset=pin.lr(), width=x_offset + pin.height() - pin.rx(),
                          height=pin.height())
            y_offset = pin.by() - vdd_difference
            self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                          width=self.bank.mid_vdd.rx() - x_offset,
                          height=pin.height())

        rails = [self.mid_vdd, self.mid_gnd]
        pin_names = ["vdd", "gnd"]
        forbidden_m2_m3 = []
        for i in range(2):
            rail = rails[i]
            power_pins = self.row_decoder_inst.get_pins(pin_names[i])
            power_pins = [x for x in power_pins if x.layer in [METAL1, METAL3]]
            for power_pin in power_pins:
                self.add_rect(power_pin.layer, vector(rail.lx(), power_pin.by()),
                              height=power_pin.height(), width=power_pin.lx() - rail.lx())
                if power_pin.layer == METAL3:
                    forbidden_m2_m3.append(power_pin)
                    via = m2m3
                else:
                    via = m1m2
                self.add_contact_center(via.layer_stack, offset=vector(rail.cx(), power_pin.cy()),
                                        size=[1, 2], rotate=90)
        fill_width = self.mid_vdd.width
        _, fill_height = self.calculate_min_m1_area(fill_width, min_height=self.m3_width,
                                                    layer=METAL3)

        wide_space = self.get_wide_space(METAL3)
        via_spacing = wide_space + self.parallel_via_space
        via_pitch = via_spacing + max(m2m3.height, fill_height)

        forbidden_m2_m3 = list(sorted(forbidden_m2_m3, key=lambda x: x.cy()))

        y_offset = via_pitch
        via_offsets = []
        if self.num_banks == 1:
            via_top = self.mid_vdd.height - via_pitch
        else:
            via_top = self.bank.bitcell_array_inst.by()
        while y_offset < via_top:
            if len(forbidden_m2_m3) > 0 and forbidden_m2_m3[0].by() <= y_offset + via_pitch:
                y_offset = forbidden_m2_m3[0].uy() + via_pitch
                forbidden_m2_m3.pop(0)
            else:
                via_offsets.append(y_offset)
                y_offset += via_pitch

        m4_power_pins = self.bank.get_pins("vdd") + self.bank.get_pins("gnd")
        m4_power_pins = [x for x in m4_power_pins if x.layer == METAL4]

        for i in range(2):
            rail = rails[i]
            for y_offset in via_offsets:
                via_offset = vector(rail.cx(), y_offset + 0.5 * fill_height)
                self.add_contact_center(m2m3.layer_stack, offset=via_offset,
                                        size=[1, 2], rotate=90)
                self.add_contact_center(m3m4.layer_stack, offset=via_offset,
                                        size=[1, 2], rotate=90)
                self.add_rect_center(METAL3, offset=via_offset, width=fill_width,
                                     height=fill_height)
            if self.num_banks == 1:
                rail_top = rail.uy()
            else:
                rail_top = self.bank.bitcell_array_inst.by()
            rect = self.add_rect(METAL4, offset=rail.ll(),
                                 width=rail.width, height=rail_top - rail.by())
            m4_power_pins.append(rect)

        self.m4_power_pins = m4_power_pins

    def route_decoder_enable(self):
        enable_rail = getattr(self.bank, "wordline_en_rail")
        enable_pin = self.row_decoder_inst.get_pin("en")

        m2_top = enable_pin.cy() + 0.5 * cross_m2m3.height
        self.add_rect(METAL2, offset=enable_rail.ul(), width=enable_rail.width,
                      height=m2_top - enable_rail.uy())
        m3_right = enable_rail.cx() + 0.5 * cross_m2m3.height
        self.add_rect(METAL3, offset=enable_pin.lr(), height=enable_pin.height(),
                      width=m3_right - enable_pin.rx())
        self.add_cross_contact_center(cross_m2m3, offset=vector(enable_rail.cx(), enable_pin.cy()))

    def route_decoder_outputs(self):
        for row in range(self.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            wl_ins = self.right_bank_inst.get_pin("dec_out[{}]".format(row))
            self.add_rect(METAL1, offset=decoder_out.lr(), height=decoder_out.height(),
                          width=wl_ins.lx() - decoder_out.rx())

    def copy_layout_pins(self):
        for i in range(self.row_addr_size):
            self.copy_layout_pin(self.row_decoder_inst, "A[{}]".format(i), "ADDR[{}]".format(i))

        right_bank = self.bank_insts[0]
        for pin_name in ["clk", "sense_trig", "precharge_trig", "read", "bank_sel"]:
            self.copy_layout_pin(right_bank, pin_name)

        for j in range(self.num_banks):
            for i in range(self.word_size):
                for pin_name in ["DATA", "MASK"]:
                    self.copy_layout_pin(self.bank_insts[j], pin_name + "[{}]".format(i),
                                         "{0}_{1}[{2}]".format(pin_name, j + 1, i))

    def route_power_grid(self):
        self.copy_layout_pin(self.bank_insts[0], "vdd")
        self.copy_layout_pin(self.bank_insts[0], "gnd")
