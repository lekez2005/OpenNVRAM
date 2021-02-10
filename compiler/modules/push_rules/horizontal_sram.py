import debug
from base import utils
from base.contact import m1m2, cross_m2m3, m2m3, m3m4, cross_m1m2
from base.contact_full_stack import ContactFullStack
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

    def add_pins(self):
        for i in range(self.num_banks * self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.bank_addr_size):
            self.add_pin("ADDR[{0}]".format(i))
        self.add_pin_list(["read", "clk", "bank_sel", "sense_trig",
                           "vdd", "gnd", "precharge_trig"])

    def create_modules(self):
        super().create_modules()
        self.row_decoder_y -= self.bank.bitcell.height

    def route_layout(self):
        super().route_layout()
        debug.info(1, "Route sram decoder enable bank")
        self.route_decoder_enable()

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
        _, fill_height = self.calculate_min_area_fill(fill_width, min_height=self.m3_width,
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

        if self.num_banks == 1:
            rail_top = self.mid_vdd.uy()
        elif self.num_banks == 2 and self.column_decoder_inst is not None:
            rail_top = self.left_col_mux_select_y
        else:
            rail_top = self.bank.bitcell_array_inst.by()
        self.add_left_power_rail_vias(via_offsets, rail_top, fill_height)

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
        _, m3_fill_width = self.calculate_min_area_fill(m3_fill_height, layer=METAL3)

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
            _, m2_fill_height = self.calculate_min_area_fill(m2_fill_width, layer=METAL2)
            offset = vector(wl_in.cx(), m3_decoder_out.cy())

            self.add_rect_center(METAL2, offset=offset,
                                 width=m2_fill_width, height=m2_fill_height)
            self.add_rect_center(METAL3, offset=offset,
                                 width=m3_fill_width, height=m3_fill_height)
            self.add_contact_center(m1m2.layer_stack, offset=offset)
            self.add_contact_center(m2m3.layer_stack, offset=offset, rotate=90)
            self.add_contact_center(m3m4.layer_stack, offset=offset, rotate=90)

    def route_power_grid(self):
        if not self.add_power_grid:
            for i in range(self.num_banks):
                self.copy_layout_pin(self.bank_insts[i], "vdd")
                self.copy_layout_pin(self.bank_insts[i], "gnd")
        else:
            metal_layers, layer_numbers = utils.get_sorted_metal_layers()
            top_layer = metal_layers[-1]
            second_top_layer = metal_layers[-2]

            # second_top to top layer via
            m_top_via = ContactFullStack(start_layer=-2, stop_layer=-1, centralize=False)
            # m4 to second_top layer vias
            all_m4_power_pins = self.m4_power_pins + self.m4_gnd_rects + self.m4_vdd_rects
            all_m4_power_widths = list(set([utils.round_to_grid(x.rx() - x.lx()) for x in all_m4_power_pins]))
            all_m4_vias = {}
            for width in all_m4_power_widths:
                all_m4_vias[width] = ContactFullStack(start_layer=3, stop_layer=-2, centralize=True,
                                                      max_width=width)
            # dimensions of vertical top layer grid
            left = min(map(lambda x: x.lx(), all_m4_power_pins)) - 0.5 * m_top_via.width
            right = max(map(lambda x: x.rx(), all_m4_power_pins)) - 0.5 * m_top_via.width
            bottom = min(map(lambda x: x.by(), all_m4_power_pins))
            top = max(map(lambda x: x.uy(), all_m4_power_pins)) - m_top_via.height

            # add top layer
            top_layer_width = m_top_via.width
            top_layer_space = self.get_wide_space(top_layer)
            top_layer_pitch = top_layer_width + top_layer_space
            top_layer_pins = []

            x_offset = left
            i = 0
            while x_offset < right:
                pin_name = "gnd" if i % 2 == 0 else "vdd"
                top_layer_pins.append(self.add_layout_pin(pin_name, top_layer, offset=vector(x_offset, bottom),
                                                          width=top_layer_width, height=top - bottom))
                x_offset += top_layer_pitch
                i += 1
            top_gnd = top_layer_pins[0::2]
            top_vdd = top_layer_pins[1::2]

            # add second_top layer
            y_offset = bottom
            rail_height = max(map(lambda x: x.height, [m_top_via] + list(all_m4_vias.values())))
            rail_space = self.get_wide_space(second_top_layer)
            rail_pitch = rail_height + rail_space

            m4_vdd_rects = self.m4_vdd_rects + [x for x in self.m4_power_pins if x.name == "vdd"]
            m4_vdd_rects = list(sorted(m4_vdd_rects, key=lambda x: x.lx()))
            m4_gnd_rects = self.m4_gnd_rects + [x for x in self.m4_power_pins if x.name == "gnd"]
            m4_gnd_rects = list(sorted(m4_gnd_rects, key=lambda x: x.lx()))

            i = 0
            while y_offset < top - m_top_via.height:
                rail_rect = self.add_rect(second_top_layer, offset=vector(left, y_offset), height=rail_height,
                                          width=right + m_top_via.width - left)
                # connect to top grid
                top_pins = top_gnd if i % 2 == 0 else top_vdd
                for top_pin in top_pins:
                    self.add_inst(m_top_via.name, m_top_via,
                                  offset=vector(top_pin.lx(), rail_rect.cy() - 0.5 * m_top_via.height))
                    self.connect_inst([])

                # connect to m4 below
                m4_rects = m4_gnd_rects if i % 2 == 0 else m4_vdd_rects
                x_offset = m4_rects[0].lx()
                for m4_rect in m4_rects:
                    if m4_rect.by() < y_offset and m4_rect.uy() > rail_rect.uy():
                        if m4_rect.lx() < x_offset:  # prevent via clash
                            continue
                        m4_rect_width = utils.round_to_grid(m4_rect.rx() - m4_rect.lx())
                        m4_via = all_m4_vias[m4_rect_width]
                        self.add_inst(m4_via.name, mod=m4_via,
                                      offset=vector(m4_rect.cx(), rail_rect.cy() - 0.5 * m4_via.height))
                        self.connect_inst([])
                        x_offset = m4_rect.cx() + 0.5 * m4_via.width + rail_space

                y_offset += rail_pitch
                i += 1

    def create_column_decoder_modules(self):
        buffer_sizes = [OPTS.predecode_sizes[0]] + OPTS.column_decoder_buffers[1:]
        if self.words_per_row == 2:
            self.column_decoder = FlopBufferHorizontal(OPTS.control_flop, OPTS.column_decoder_buffers,
                                                       dummy_indices=[0, 2])
        elif self.words_per_row == 4:
            self.column_decoder = predecode2x4_horizontal(use_flops=True, buffer_sizes=buffer_sizes)
        else:
            self.column_decoder = predecode3x8_horizontal(use_flops=True, buffer_sizes=buffer_sizes)

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
