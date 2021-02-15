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

    def create_modules(self):
        super().create_modules()
        self.row_decoder_y -= self.bank.bitcell.height

    def create_column_decoder_modules(self):
        buffer_sizes = [OPTS.predecode_sizes[0]] + OPTS.column_decoder_buffers[1:]
        if self.words_per_row == 2:
            self.column_decoder = FlopBufferHorizontal(OPTS.control_flop, OPTS.column_decoder_buffers,
                                                       dummy_indices=[0, 2])
        elif self.words_per_row == 4:
            self.column_decoder = predecode2x4_horizontal(use_flops=True, buffer_sizes=buffer_sizes)
        else:
            self.column_decoder = predecode3x8_horizontal(use_flops=True, buffer_sizes=buffer_sizes)

    def route_layout(self):
        super().route_layout()
        debug.info(1, "Route sram decoder enable bank")
        self.route_decoder_enable()

    @staticmethod
    def get_bank_class():
        return HorizontalBank

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
                              height=pin.height(), width=pin.lx() + m2m3.height - x_offset)
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
            self.add_rect(METAL3, offset=vector(x_offset, y_offset), width=pin.height(),
                          height=pin.by() - y_offset)
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

    def route_predecoder_col_mux_power_pin(self, pin, rail):
        flop_height = self.column_decoder.flop.height
        if (pin.layer == METAL1 and
                pin.by() - self.column_decoder_inst.by() > self.col_addr_size * flop_height):
            x_right = pin.lx()
            via = m1m2
            layer = METAL1
        else:
            x_right = self.column_decoder_inst.lx() + self.column_decoder.in_inst[0].lx()
            via = m2m3
            layer = METAL3
        self.add_rect(layer, offset=vector(rail.lx(), pin.by()),
                      width=x_right - rail.lx(), height=pin.height())
        self.add_contact_center(via.layer_stack, offset=vector(rail.cx(), pin.cy()),
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
            for tap_inst in self.bank.wordline_driver.tap_insts:
                y_top = self.bank.wordline_driver_inst.by() + tap_inst.by() + implant_extension
                self.add_rect(NIMP, offset=vector(x_start, y_offset), width=x_end - x_start,
                              height=y_top - y_offset)
                y_offset = self.bank.wordline_driver_inst.by() + tap_inst.uy() - implant_extension
            y_top = (self.bank.wordline_driver_inst.by()
                     + self.bank.wordline_driver_inst.mod.buffer_insts[-1].uy() + implant_extension)
            self.add_rect(NIMP, offset=vector(x_start, y_offset), width=x_end - x_start,
                          height=y_top - y_offset)
