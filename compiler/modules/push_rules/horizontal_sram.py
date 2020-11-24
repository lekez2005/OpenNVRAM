import debug
from base.contact import m1m2, cross_m2m3, m2m3, m3m4, cross_m1m2
from base.design import METAL2, METAL3, METAL1, METAL4, NIMP
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.push_rules.flop_buffer_horizontal import FlopBufferHorizontal
from modules.push_rules.horizontal_bank import HorizontalBank
from modules.push_rules.predecode2x4_horizontal import predecode2x4_horizontal
from modules.push_rules.predecode3x8_horizontal import predecode3x8_horizontal
from modules.shared_decoder.cmos_sram import CmosSram


class HorizontalSram(CmosSram):
    rotation_for_drc = GDS_ROT_270
    config_template = "config_push_hs_{}"

    def __init__(self, word_size, num_words, num_banks, name, words_per_row=None):
        """Words will be split across banks in case of two banks"""
        assert num_banks in [1, 2], "Only one or two banks supported"
        assert word_size % 2 == 0, "Word-size must be even"
        assert words_per_row in [1, 2, 4, 8], "Max 8 words per row supported"
        if num_banks == 2:
            word_size = int(word_size / 2)
        super().__init__(word_size, num_words, num_banks, name, words_per_row)
        # restore word-size
        self.word_size = num_banks * self.word_size

    def add_pins(self):
        for i in range(self.num_banks * self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.bank_addr_size):
            self.add_pin("ADDR[{0}]".format(i))
        self.add_pin_list(["read", "clk", "bank_sel", "sense_trig",
                           "vdd", "gnd", "precharge_trig"])

    def add_modules(self):
        debug.info(1, "Add sram modules")
        self.right_bank_inst = self.bank_inst = self.add_bank(0, vector(0, 0), x_flip=0, y_flip=0)
        self.bank_insts = [self.right_bank_inst]
        self.add_col_decoder()
        self.add_row_decoder()
        self.add_power_rails()
        if self.num_banks == 2:
            x_offset = self.get_left_bank_x()
            self.left_bank_inst = self.add_bank(1, vector(x_offset, 0), x_flip=0, y_flip=-1)
            self.bank_insts = [self.right_bank_inst, self.left_bank_inst]

    def route_layout(self):
        super().route_layout()
        debug.info(1, "Route sram decoder enable bank")
        self.route_decoder_enable()
        debug.info(1, "Route left bank sram power")
        self.route_left_bank_power()
        self.fill_decoder_wordline_space()
        debug.info(1, "Route sram power grid")
        self.route_power_grid()

    def create_bank(self):
        debug.info(1, "Creating right bank")
        self.bank = HorizontalBank(name="bank", word_size=self.word_size,
                                   num_words=self.num_words_per_bank,
                                   words_per_row=self.words_per_row, num_banks=self.num_banks)
        self.add_mod(self.bank)
        if self.num_banks == 2:
            debug.info(1, "Creating left bank")
            self.left_bank = HorizontalBank(name="left_bank", word_size=self.word_size,
                                            num_words=self.num_words_per_bank,
                                            words_per_row=self.words_per_row,
                                            num_banks=self.num_banks,
                                            adjacent_bank=self.bank)
            self.add_mod(self.left_bank)

    def create_column_decoder(self):
        super().create_column_decoder()
        if self.words_per_row > 1:
            # decoder clock is always connected to clk_buf_1
            self.col_decoder_connections = [x if not (x == "clk_buf_2") else "clk_buf_1"
                                            for x in self.col_decoder_connections]

    def get_bank_mod(self, bank_num):
        return self.bank if bank_num == 0 else self.left_bank

    def get_bank_connections(self, bank_num):

        connections = []
        for i in range(self.word_size):
            connections.append("DATA[{0}]".format(bank_num * self.word_size + i))
            connections.append("MASK[{0}]".format(bank_num * self.word_size + i))
        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                connections.append("sel[{}]".format(i))
        for i in range(self.num_rows):
            connections.append("dec_out[{}]".format(i))

        other_connections = ["bank_sel", "read", "clk", "sense_trig", "precharge_trig"]
        if bank_num == 0:
            other_connections.extend(["clk_buf_1", "clk_bar_1", "vdd", "gnd", "wordline_en"])
        else:
            other_connections.extend(["clk_buf_2", "clk_bar_2", "vdd", "gnd"])
        return connections + other_connections

    def get_row_decoder_connections(self):
        connections = super().get_row_decoder_connections() + ["wordline_en"]
        return connections

    def add_row_decoder(self):

        left_most_rail_x = self.bank.leftmost_rail.offset.x
        if self.column_decoder_inst is not None:
            if self.bank.col_decoder_is_left:
                left_most_rail_x -= (1 + self.words_per_row) * self.bus_pitch
            else:
                left_most_rail_x -= self.words_per_row * self.bus_pitch
        elif self.bank.read_buf_inst.uy() < self.bank.control_buffers_inst.by():
            left_most_rail_x -= 2 * self.bus_pitch
        max_predecoder_x = (left_most_rail_x - self.get_wide_space(METAL2) -
                            self.row_decoder.width)
        max_row_decoder_x = self.bank.wordline_driver_inst.lx() - self.row_decoder.row_decoder_width
        x_offset = min(max_predecoder_x, max_row_decoder_x)

        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.row_decoder,
                                              offset=vector(x_offset, self.row_decoder_y))

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

    def join_bank_controls(self):
        if self.single_bank:
            return
        pin_names = ["precharge_trig", "sense_trig", "clk", "read", "bank_sel"]
        bottom_inst_y = self.bank.bank_sel_buf_inst.by()
        if self.column_decoder_inst is not None:
            bottom_inst_y = min(bottom_inst_y, self.column_decoder_inst.by())
        cross_clk_rail_y = (bottom_inst_y - self.get_wide_space(METAL2)
                            - self.bus_pitch)
        y_offset = cross_clk_rail_y - (len(pin_names) + 1) * self.bus_pitch
        via_extension = 0.5 * (cross_m2m3.height - cross_m2m3.contact_width)
        for i in range(len(pin_names)):
            left_pin = self.bank_insts[1].get_pin(pin_names[i])
            right_pin = self.bank_insts[0].get_pin(pin_names[i])
            for pin in [left_pin, right_pin]:
                self.add_cross_contact_center(cross_m2m3,
                                              offset=vector(pin.cx(),
                                                            y_offset + 0.5 * self.bus_width))
                rail_bottom = y_offset + 0.5 * self.bus_width - 0.5 * cross_m2m3.height
                if rail_bottom < pin.by():
                    self.add_rect(pin.layer, offset=vector(pin.lx(), rail_bottom),
                                  width=pin.width(), height=pin.by() - rail_bottom)
            self.add_rect(METAL3, offset=vector(left_pin.lx() - via_extension, y_offset),
                          height=self.bus_width,
                          width=right_pin.rx() - left_pin.lx() + 2 * via_extension)

            y_offset += self.bus_pitch

    def route_decoder_power(self):
        # connect wordline driver gnd to decoder gnd
        row_decoder_right = self.row_decoder_inst.lx() + self.row_decoder.and_insts[0].rx()
        for pin in self.bank.wordline_driver_inst.get_pins("gnd"):
            self.add_contact_center(m2m3.layer_stack,
                                    offset=vector(pin.lx() + 0.5 * m2m3.height, pin.cy()),
                                    rotate=90)
            if pin.lx() > row_decoder_right:
                x_offset = row_decoder_right
                self.add_rect(METAL2, offset=vector(x_offset, pin.by()),
                              height=pin.height(), width=pin.lx() - x_offset)
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

        if self.words_per_row > 1:
            forbidden_m2_m3.extend(self.column_decoder_inst.get_pins("vdd"))
            forbidden_m2_m3.extend(self.column_decoder_inst.get_pins("gnd"))

        forbidden_m2_m3 = list(sorted(forbidden_m2_m3, key=lambda x: x.cy()))

        y_offset = self.bank.bank_sel_buf_inst.by()
        via_offsets = []
        if self.num_banks == 1:
            via_top = self.mid_vdd.height - via_pitch
        elif self.num_banks == 2 and self.column_decoder_inst is not None:
            via_top = self.left_col_mux_select_y
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
            elif self.num_banks == 2 and self.column_decoder_inst is not None:
                rail_top = self.left_col_mux_select_y
            else:
                rail_top = self.bank.bitcell_array_inst.by()
            rect = self.add_rect(METAL4, offset=rail.ll(),
                                 width=rail.width, height=rail_top - rail.by())
            m4_power_pins.append(rect)

        self.m4_power_pins = m4_power_pins

    def route_left_bank_power(self):
        if self.num_banks == 1:
            return
        rails = [self.mid_gnd, self.mid_vdd]
        pin_names = ["gnd", "vdd"]
        for i in range(2):
            rail = rails[i]
            for pin in self.left_bank.wordline_driver_inst.get_pins(pin_names[i]):
                if not pin.layer == METAL3:
                    continue
                pin_x = self.left_bank_inst.rx() - pin.lx()
                self.add_rect(METAL3, offset=vector(pin_x, pin.by()), height=pin.height(),
                              width=rail.rx() - pin_x)
                self.add_contact_center(m2m3.layer_stack, offset=vector(rail.cx(), pin.cy()),
                                        rotate=90, size=[1, 2])

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
        m3_fill_height = self.bus_width
        _, m3_fill_width = self.calculate_min_m1_area(m3_fill_height, layer=METAL3)

        for row in range(self.num_rows):
            decoder_outs = self.row_decoder_inst.get_pins("decode[{}]".format(row))
            m1_decoder_out = [x for x in decoder_outs if x.layer == METAL1][0]

            wl_in = self.right_bank_inst.get_pin("dec_out[{}]".format(row))
            self.add_rect(METAL1, offset=m1_decoder_out.lr(), height=m1_decoder_out.height(),
                          width=wl_in.lx() - m1_decoder_out.rx())
            if self.num_banks == 1:
                continue
            m3_decoder_out = [x for x in decoder_outs if x.layer == METAL3][0]
            wl_in = self.left_bank_inst.get_pin("dec_out[{}]".format(row))
            self.add_contact_center(m3m4.layer_stack,
                                    offset=vector(m3_decoder_out.cx(), m3_decoder_out.cy()),
                                    rotate=90)
            right_x = m3_decoder_out.cx() + 0.5 * m3m4.height
            x_offset = wl_in.cx() - 0.5 * m3m4.height
            self.add_rect(METAL4,
                          offset=vector(x_offset, m3_decoder_out.cy() - 0.5 * self.bus_width),
                          width=right_x - x_offset, height=self.bus_width)

            m2_fill_width = m2m3.height
            _, m2_fill_height = self.calculate_min_m1_area(m2_fill_width, layer=METAL2)
            offset = vector(wl_in.cx(), m3_decoder_out.cy())

            self.add_rect_center(METAL2, offset=offset,
                                 width=m2_fill_width, height=m2_fill_height)
            self.add_rect_center(METAL3, offset=offset,
                                 width=m3_fill_width, height=m3_fill_height)
            self.add_contact_center(m1m2.layer_stack, offset=offset)
            self.add_contact_center(m2m3.layer_stack, offset=offset, rotate=90)
            self.add_contact_center(m3m4.layer_stack, offset=offset, rotate=90)

    def copy_layout_pins(self):
        for i in range(self.row_addr_size):
            self.copy_layout_pin(self.row_decoder_inst, "A[{}]".format(i), "ADDR[{}]".format(i))

        right_bank = self.bank_insts[0]
        for pin_name in ["clk", "sense_trig", "precharge_trig", "read", "bank_sel"]:
            self.copy_layout_pin(right_bank, pin_name)

        for j in range(self.num_banks):
            for i in range(self.word_size):
                for pin_name in ["DATA", "MASK"]:
                    bit_index = j * self.word_size + i
                    self.copy_layout_pin(self.bank_insts[j], pin_name + "[{}]".format(i),
                                         "{0}[{1}]".format(pin_name, bit_index))

    def route_power_grid(self):
        for i in range(self.num_banks):
            self.copy_layout_pin(self.bank_insts[i], "vdd")
            self.copy_layout_pin(self.bank_insts[i], "gnd")

    def create_column_decoder_modules(self):
        buffer_sizes = [OPTS.predecode_sizes[0]] + OPTS.column_decoder_buffers[1:]
        if self.words_per_row == 2:
            self.column_decoder = FlopBufferHorizontal(OPTS.control_flop, OPTS.column_decoder_buffers,
                                                       dummy_indices=[0, 2])
        elif self.words_per_row == 4:
            self.column_decoder = predecode2x4_horizontal(use_flops=True, buffer_sizes=buffer_sizes)
        else:
            self.column_decoder = predecode3x8_horizontal(use_flops=True, buffer_sizes=buffer_sizes)

    def add_col_decoder(self):
        if self.words_per_row == 1:
            return
        # check if there is enough space between row decoder and read_buf
        # if so, place above read_buf, otherwise, place to the left of read_buf
        if self.bank.col_decoder_is_left:
            left_most_rail_x = self.bank.read_buf_inst.lx() - 4 * self.bus_pitch
        else:
            left_most_rail_x = self.bank.leftmost_rail.offset.x
        column_decoder_y = self.bank.bank_sel_buf_inst.by() + (self.bank.col_decoder_y - self.bank.control_flop_y)

        column_decoder = self.column_decoder

        col_decoder_x = left_most_rail_x - (1 + self.words_per_row) * self.bus_pitch - column_decoder.width
        self.column_decoder_inst = self.add_inst("col_decoder", mod=self.column_decoder,
                                                 offset=vector(col_decoder_x, column_decoder_y))
        self.connect_inst(self.col_decoder_connections)

    def route_flop_column_decoder(self):
        self.route_col_decoder_clock()

        # outputs
        out_pin = self.column_decoder_inst.get_pin("dout")
        out_bar_pin = self.column_decoder_inst.get_pin("dout_bar")
        y_offsets = [out_pin.cy(), out_pin.cy() + self.bus_pitch]
        self.col_decoder_outputs = []

        self.route_col_decoder_to_rail(output_pins=[out_bar_pin, out_pin], rail_offsets=y_offsets)

        self.route_col_decoder_outputs()
        self.route_col_decoder_power()
        self.copy_layout_pin(self.column_decoder_inst, "din", "ADDR[{}]".format(self.addr_size - self.num_banks))

    def route_predecoder_column_decoder(self):
        self.route_col_decoder_clock()
        # address pins
        all_addr_pins = ["ADDR[{}]".format(self.addr_size - self.num_banks - i) for i in range(self.col_addr_size)]
        all_addr_pins = list(reversed(all_addr_pins))
        for i in range(self.col_addr_size):
            self.copy_layout_pin(self.column_decoder_inst, "flop_in[{}]".format(i), all_addr_pins[i])

        #
        self.route_col_decoder_to_rail()
        self.route_col_decoder_outputs()
        self.route_col_decoder_power()

    def route_col_decoder_clock(self):
        # route clk
        row_decoder_clk = min(self.row_decoder_inst.get_pins("clk"), key=lambda x: x.cy())
        row_decoder_vdd = min(self.row_decoder_inst.get_pins("vdd"), key=lambda x: x.cy())
        decoder_clk_y = row_decoder_vdd.by() - self.bus_pitch
        self.add_rect(METAL2, offset=vector(row_decoder_clk.lx(), decoder_clk_y), width=row_decoder_clk.width(),
                      height=row_decoder_clk.by() - decoder_clk_y)
        self.add_cross_contact_center(cross_m2m3, offset=vector(row_decoder_clk.cx(),
                                                                decoder_clk_y + 0.5 * self.bus_width))
        x_offset = self.column_decoder_inst.lx() - self.bus_pitch
        self.add_rect(METAL3, offset=vector(x_offset, decoder_clk_y), height=self.bus_width,
                      width=row_decoder_clk.cx() - x_offset)
        col_decoder_clk = self.column_decoder_inst.get_pin("clk")
        y_offset = col_decoder_clk.uy() - self.bus_width
        self.add_cross_contact_center(cross_m2m3, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                decoder_clk_y + 0.5 * self.bus_width))
        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=decoder_clk_y - y_offset,
                      width=self.bus_width)
        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=self.bus_width,
                      width=col_decoder_clk.lx() - x_offset)

    def route_col_decoder_to_rail(self, output_pins=None, rail_offsets=None):
        if output_pins is None:
            output_pins = [self.column_decoder_inst.get_pin("out[{}]".format(i)) for i in range(self.words_per_row)]
        if rail_offsets is None:
            rail_offsets = [x.cy() for x in output_pins]

        if self.bank.col_decoder_is_left:
            base_x = self.column_decoder_inst.rx() + self.bus_pitch
            # using by() because mirror. TODO fix by()/uy() post offset_all_coordinates
            base_y = (self.bank.read_buf_inst.by() + self.bank.rail_space_above_controls
                      - self.words_per_row * self.bus_pitch)
            rails_y = [base_y + i * self.bus_pitch for i in range(self.words_per_row)]

            x_offset = self.bank.leftmost_rail.offset.x - (1 + self.words_per_row) * self.bus_pitch
            rails_x = [x_offset + i * self.bus_pitch for i in range(self.words_per_row)]
        else:
            base_x = self.bank.leftmost_rail.offset.x - self.words_per_row * self.bus_pitch
            rails_y = []
            rails_x = []
        x_offsets = [base_x + i * self.bus_pitch for i in range(self.words_per_row)]

        self.col_decoder_outputs = []
        for i in range(self.words_per_row):
            output_pin = output_pins[i]
            x_offset = x_offsets[i]
            y_offset = rail_offsets[i]
            if i == 0 and self.words_per_row == 2:
                self.add_contact_center(m1m2.layer_stack, offset=vector(output_pin.cx(),
                                                                        y_offset + 0.5 * self.bus_width))
                self.add_rect(METAL2, offset=vector(output_pin.cx(), y_offset),
                              height=self.bus_width, width=x_offset - output_pin.cx())
            else:
                self.add_rect(METAL1, offset=vector(output_pin.cx(), y_offset), width=x_offset - output_pin.cx(),
                              height=self.bus_width)
                self.add_cross_contact_center(cross_m1m2, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                        y_offset + 0.5 * self.bus_width),
                                              rotate=True)
            if not self.bank.col_decoder_is_left:
                self.col_decoder_outputs.append(self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                                                              width=self.bus_width, height=self.bus_width))
            else:
                _, fill_height = self.calculate_min_m1_area(self.bus_width, layer=METAL2)
                rail_y = rails_y[i]
                m2_height = rail_y - y_offset
                self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=m2_height, width=self.bus_width)

                if abs(m2_height) < fill_height:
                    self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=fill_height, width=self.bus_width)

                self.add_cross_contact_center(cross_m2m3, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                        rail_y + 0.5 * self.bus_width))
                self.add_rect(METAL3, offset=vector(x_offset, rail_y), width=rails_x[i] - x_offset,
                              height=self.bus_width)
                self.add_cross_contact_center(cross_m2m3, offset=vector(rails_x[i] + 0.5 * self.bus_width,
                                                                        rail_y + 0.5 * self.bus_width))
                self.col_decoder_outputs.append(self.add_rect(METAL2, offset=vector(rails_x[i], rail_y),
                                                              width=self.bus_width, height=self.bus_width))

    def route_col_decoder_outputs(self):
        if self.num_banks == 2:
            top_predecoder_inst = max(self.row_decoder.pre2x4_inst + self.row_decoder.pre3x8_inst,
                                      key=lambda x: x.uy())
            # place rails just above the input flops
            num_flops = top_predecoder_inst.mod.num_inputs
            y_space = top_predecoder_inst.get_pins("vdd")[0].height() + self.get_wide_space(METAL3) + self.bus_space
            self.left_col_mux_select_y = (self.row_decoder_inst.by() + top_predecoder_inst.by()
                                          + num_flops * top_predecoder_inst.mod.flop.height + y_space)

        for i in range(self.words_per_row):
            sel_pin = self.right_bank_inst.get_pin("sel[{}]".format(i))
            rail = self.col_decoder_outputs[i]
            self.add_rect(METAL2, offset=rail.ul(), width=self.bus_width, height=sel_pin.cy() - rail.uy())
            self.add_rect(METAL1, offset=vector(rail.lx(), sel_pin.cy() - 0.5 * self.bus_width),
                          width=sel_pin.lx() - rail.lx(), height=self.bus_width)
            self.add_cross_contact_center(cross_m1m2, offset=vector(rail.cx(), sel_pin.cy()), rotate=True)

            if self.num_banks == 2:
                # route to the left
                x_start = self.left_bank_inst.rx() - self.left_bank.leftmost_rail.offset.x
                x_offset = x_start + (1 + i) * self.bus_pitch

                y_offset = self.left_col_mux_select_y + i * self.bus_pitch
                self.add_rect(METAL2, offset=vector(rail.lx(), sel_pin.cy()), width=self.bus_width,
                              height=y_offset - sel_pin.cy())
                self.add_cross_contact_center(cross_m2m3, offset=vector(rail.cx(), y_offset + 0.5 * self.bus_width))
                self.add_rect(METAL3, offset=vector(x_offset, y_offset), height=self.bus_width,
                              width=rail.lx() - x_offset)
                self.add_cross_contact_center(cross_m2m3, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                        y_offset + 0.5 * self.bus_width))
                sel_pin = self.left_bank_inst.get_pin("sel[{}]".format(i))
                self.add_rect(METAL2, offset=vector(x_offset, sel_pin.cy()), width=self.bus_width,
                              height=y_offset - sel_pin.cy())
                self.add_cross_contact_center(cross_m1m2, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                        sel_pin.cy()), rotate=True)
                self.add_rect(METAL1, offset=sel_pin.lr(), height=sel_pin.height(),
                              width=x_offset - sel_pin.rx())

    def route_col_decoder_power(self):
        rails = [self.mid_vdd, self.mid_gnd]
        pin_names = ["vdd", "gnd"]
        for i in range(2):
            pin_name = pin_names[i]
            if self.words_per_row == 2:
                y_shift = self.column_decoder_inst.by() + self.column_decoder.flop_inst.by()
                x_shift = self.column_decoder_inst.lx() + self.column_decoder.flop_inst.lx()
                pins = self.column_decoder.flop.get_pins(pin_name)
                via = m2m3
                for pin in pins:
                    pin_y = pin.by() + y_shift
                    self.add_rect(pin.layer, offset=vector(rails[i].lx(), pin_y),
                                  height=pin.height(), width=pin.lx() + x_shift - rails[i].lx())
                    self.add_contact_center(via.layer_stack, offset=vector(rails[i].cx(), pin_y + 0.5 * pin.height()),
                                            size=[1, 2], rotate=90)
            else:
                flop_height = self.column_decoder.flop.height
                for pin in self.column_decoder_inst.get_pins(pin_name):

                    if pin.by() - self.column_decoder_inst.by() > self.col_addr_size * flop_height:
                        x_right = pin.lx()
                        via = m1m2
                        layer = METAL1
                    else:
                        x_right = self.column_decoder_inst.lx() + self.column_decoder.in_inst[0].lx()
                        via = m2m3
                        layer = METAL3
                    self.add_rect(layer, offset=vector(rails[i].lx(), pin.by()),
                                  width=x_right - rails[i].lx(), height=pin.height())
                    self.add_contact_center(via.layer_stack, offset=vector(rails[i].cx(), pin.cy()),
                                            size=[1, 2], rotate=90)

    def fill_decoder_wordline_space(self):
        and_inst = self.row_decoder.and_insts[0]
        buffer_inst = self.bank.wordline_driver_inst.mod.buffer_insts[0]
        buffer_inv_inst = self.bank.wordline_driver_inst.mod.buffer.module_insts[0]
        and_implant = max(and_inst.mod.get_layer_shapes(NIMP), key=lambda x: x.rx())
        buffer_implant = min(buffer_inv_inst.mod.get_layer_shapes(NIMP), key=lambda x: x.lx())

        implant_extension = - and_implant.by()

        x_start = self.row_decoder_inst.lx() + and_inst.lx() + and_implant.rx()
        x_end = (self.bank.wordline_driver_inst.lx() + buffer_inst.lx()
                 + buffer_inv_inst.lx() + buffer_implant.lx())
        if x_end > x_start:
            y_base = self.bank.wordline_driver_inst.by() + buffer_inst.by() - implant_extension
            y_offset = y_base
            for tap_inst in self.bank.wordline_buffer.tap_insts:
                y_top = self.bank.wordline_driver_inst.by() + tap_inst.by() + implant_extension
                self.add_rect(NIMP, offset=vector(x_start, y_offset), width=x_end - x_start,
                              height=y_top - y_offset)
                y_offset = self.bank.wordline_driver_inst.by() + tap_inst.uy() - implant_extension
            y_top = (self.bank.wordline_driver_inst.by()
                     + self.bank.wordline_driver_inst.mod.buffer_insts[-1].uy() + implant_extension)
            self.add_rect(NIMP, offset=vector(x_start, y_offset), width=x_end - x_start,
                          height=y_top - y_offset)
