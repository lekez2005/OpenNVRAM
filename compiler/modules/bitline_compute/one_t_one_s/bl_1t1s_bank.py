import debug
from base import utils
from base.contact import m2m3, m3m4, cross_m2m3, contact, cross_contact, cross_m3m4
from base.design import NWELL, METAL5, METAL4, METAL2, METAL3, METAL1
from base.vector import vector
from globals import OPTS

from modules.baseline_bank import BaselineBank, JOIN_BOT_ALIGN, LEFT_FILL, RIGHT_FILL
from modules.bitline_compute.bl_bank import BlBank
from modules.bitline_compute.one_t_one_s.bl_1t1s_decoder_logic import Bl1t1sDecoderLogic
from modules.mram.sotfet.mram_bank import RwlWwlMixin

if OPTS.separate_vdd_wordline:
    from modules.bank_mixins import WordlineVoltageMixin
else:
    class WordlineVoltageMixin:
        pass

m4m5 = contact(("metal4", "via4", METAL5))
m5m6 = contact((METAL5, "via5", "metal6"))

cross_m4m5 = cross_contact(m4m5.layer_stack)
cross_m5m6 = cross_contact(m5m6.layer_stack)


class Bl1t1sBank(WordlineVoltageMixin, RwlWwlMixin, BlBank):
    def create_modules(self):
        self.decoder_logic = Bl1t1sDecoderLogic(num_rows=self.num_rows)
        self.add_mod(self.decoder_logic)
        self.create_wordline_drivers()
        BaselineBank.create_modules(self)

    def get_control_flops_offset(self):
        self.words_per_row = 2
        x_offset, y_offset = super().get_control_flops_offset()
        self.words_per_row = 1
        return x_offset, y_offset

    def get_sense_amp_array_y(self):
        y_space = self.calculate_bitcell_aligned_spacing(self.sense_amp_array,
                                                         self.write_driver_array, num_rails=0)
        return self.write_driver_array_inst.uy() + y_space

    def get_bitcell_array_connections(self):
        return self.connections_from_mod(self.bitcell_array, [])

    def get_wwl_connections(self):
        connections = RwlWwlMixin.get_wwl_connections(self)
        if OPTS.separate_vdd_wordline:
            return WordlineVoltageMixin.update_wordline_driver_connections(self, connections)
        return connections

    def add_wordline_driver(self):
        super().add_wordline_driver()
        self.wordline_driver_inst = min([self.rwl_driver_inst, self.wwl_driver_inst],
                                        key=lambda x: x.lx())
        self.wordline_driver_inst.mod.add_body_taps()
        self.add_decoder_logic()

    def get_write_driver_array_connection_replacements(self):
        replacements = super().get_write_driver_array_connection_replacements()
        replacements.extend([("bl_sel", "sel[0]"), ("br_sel", "sel[1]")])
        return replacements

    def route_bitcell(self):
        self.route_bitcell_array_power()
        for row in range(self.num_rows):
            for pin_name, inst in zip(["wwl", "rwl"],
                                      [self.wwl_driver_inst, self.rwl_driver_inst]):
                bitcell_pin = self.bitcell_array_inst.get_pin(f"{pin_name}[{row}]")
                driver_pin = inst.get_pin(f"wl[{row}]")
                if bitcell_pin.cy() > driver_pin.cy():
                    y_offset = driver_pin.uy()
                else:
                    y_offset = driver_pin.by()
                self.add_rect(METAL2, vector(driver_pin.lx(), y_offset),
                              width=driver_pin.width(),
                              height=bitcell_pin.cy() - y_offset)
                self.add_cross_contact_center(cross_m2m3,
                                              vector(driver_pin.cx(), bitcell_pin.cy()),
                                              fill=False)
                x_offset = driver_pin.cx() - 0.5 * m2m3.h_2
                self.add_rect(METAL3, vector(x_offset, bitcell_pin.by()),
                              width=bitcell_pin.lx() - x_offset,
                              height=bitcell_pin.height())

    def add_pins(self):
        super().add_pins()
        self.add_pin_list(["sel[0]", "sel[1]"])
        if OPTS.separate_vdd_wordline:
            self.add_pin("vdd_wordline")

    def add_pin(self, name, pin_type=None):
        if name in ["diff", "diffb"]:
            if name not in self.sense_amp_array.pins:
                return
        super().add_pin(name, pin_type)

    def fill_between_wordline_drivers(self):
        pass

    def get_decoder_logic_x(self):
        # space based on nwell
        tap_inst = self.wordline_driver_inst.mod.body_tap_insts[0]
        tap_nwell = tap_inst.get_max_shape(NWELL, "lx", recursive=True)

        logic_inst = self.decoder_logic.en_bar_insts[0]
        logic_nwell = logic_inst.get_max_shape(NWELL, "rx", recursive=True)

        space = self.get_parallel_space(NWELL)
        x_offset = (tap_nwell.lx() + self.wordline_driver_inst.lx() - space -
                    logic_nwell.rx())
        # space based on power rails
        tap_x = self.rwl_driver_inst.lx() + self.rwl_driver.body_tap_insts[0].lx()
        m2_space = self.wide_power_space
        rail_x = tap_x - m2_space - self.vdd_rail_width
        self.decoder_logic_vdd_offset = rail_x

        return min(x_offset, rail_x - m2_space - self.decoder_logic.width)

    def get_bitcell_array_y_offset(self):
        """Get y_offset of bitcell array"""
        y_space = self.calculate_bitcell_aligned_spacing(self.bitcell_array,
                                                         self.precharge_array, num_rails=1)
        return self.precharge_array_inst.uy() + y_space

    def route_precharge(self):
        """precharge bitlines to bitcell bitlines
            col_mux or sense amp bitlines to precharge bitlines"""
        debug.info(1, "Route Precharge")
        self.route_all_instance_power(self.precharge_array_inst)
        self.join_bitlines(self.bitcell_array_inst, "", self.sense_amp_array_inst, "",
                           rect_align=JOIN_BOT_ALIGN)

        y_shift = - (self.get_parallel_space(METAL4) + 0.5 * m3m4.h_2)

        for pin_name in ["blb", "brb"]:
            for col in range(self.num_cols):
                sense_pin = max(self.sense_amp_array_inst.get_pins(f"{pin_name}[{col}]"),
                                key=lambda x: x.uy())
                bitcell_pin = self.bitcell_array_inst.get_pin(f"{pin_name}[{col}]")
                y_offset = bitcell_pin.by() - sense_pin.width() + y_shift
                self.add_rect(sense_pin.layer, sense_pin.ul(), width=sense_pin.width(),
                              height=y_offset + sense_pin.width() - sense_pin.uy())
                self.add_rect(sense_pin.layer, vector(bitcell_pin.cx(), y_offset),
                              height=sense_pin.width(), width=sense_pin.cx() - bitcell_pin.cx())
                self.add_rect(bitcell_pin.layer, vector(bitcell_pin.lx(), y_offset),
                              width=bitcell_pin.width(), height=bitcell_pin.by() - y_offset)

    def get_bitline_pins(self, top_instance, bottom_instance, top_suffix="",
                         bottom_suffix="", word_size=None, pin_names=None):
        if word_size is None:
            word_size = self.word_size
        pin_names = pin_names or ["bl", "br"]

        all_pins = []
        for i in range(len(pin_names)):
            pin_name = pin_names[i]
            top_pins = [min(top_instance.get_pins(f"{pin_name}{top_suffix}[{bit}]"),
                            key=lambda x: x.by()) for bit in range(word_size)]
            bottom_pins = [max(bottom_instance.get_pins(f"{pin_name}{bottom_suffix}[{bit}]"),
                               key=lambda x: x.uy()) for bit in range(word_size)]

            all_pins.append((top_pins, bottom_pins))
        return all_pins

    def route_sense_amp(self):
        self.data_bus_y = self.control_buffers_inst.by()
        self.route_all_instance_power(self.sense_amp_array_inst)
        self.route_sense_amp_vref()
        self.route_and_nor_pins()
        self.join_bitlines(self.sense_amp_array_inst, "",
                           self.write_driver_array_inst, "")
        self.join_bitlines(self.sense_amp_array_inst, "b",
                           self.write_driver_array_inst, "b")
        self.join_bitlines(self.sense_amp_array_inst, "", self.write_driver_array_inst,
                           "", pin_names=["and"])
        self.join_bitlines(self.sense_amp_array_inst, "", self.write_driver_array_inst,
                           "", pin_names=["nor"])

    def route_and_nor_pins(self):
        y_offset = self.get_m2_m3_below_instance(self.write_driver_array_inst, index=1)
        via_y = y_offset + 0.5 * m5m6.h_2

        fill_height = m5m6.h_2
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL5)

        via_extension = self.get_drc_by_layer(METAL5, "wide_metal_via_extension")

        for pin_name in ["and", "nor"]:
            for word in range(self.word_size):
                pin = min(self.write_driver_array_inst.get_pins(f"{pin_name}[{word}]"),
                          key=lambda x: x.by())

                m6_y = via_y - 0.5 * m5m6.h_2
                self.add_rect("metal6", vector(pin.lx(), m6_y), width=pin.width(),
                              height=pin.by() - m6_y)
                self.add_contact_center(m5m6.layer_stack, vector(pin.cx(), via_y))
                pin_top = via_y

                if pin_name == "and":
                    reference_pin = self.write_driver_array_inst.get_pin(f"bl[{word}]")
                    fill_x = reference_pin.cx() - 0.5 * m5m6.w_1 - via_extension
                    fill_width_ = max(fill_x + fill_width, pin.cx() +
                                      0.5 * m5m6.w_1 + via_extension) - fill_x
                else:
                    reference_pin = self.write_driver_array_inst.get_pin(f"br[{word}]")
                    fill_x = reference_pin.cx() + 0.5 * m5m6.w_1 + via_extension - fill_width
                    fill_width_ = fill_width

                self.add_contact_center(m4m5.layer_stack, vector(reference_pin.cx(), via_y))

                self.add_rect(METAL5, vector(fill_x, via_y - 0.5 * fill_height),
                              width=fill_width_, height=fill_height)

                pin_x = reference_pin.cx() - 0.5 * self.m4_width
                self.add_layout_pin(pin.name, METAL4, vector(pin_x, self.data_bus_y),
                                    width=self.m4_width, height=pin_top - self.data_bus_y)

    def route_write_driver(self):
        super().route_write_driver()
        for source_pin, dest_pin in [("bl_sel", "sel[0]"), ("br_sel", "sel[1]")]:
            driver_pin = self.write_driver_array_inst.get_pin(source_pin)
            pin_x = self.leftmost_rail.lx()
            self.add_layout_pin(dest_pin, driver_pin.layer, vector(pin_x, driver_pin.by()),
                                height=driver_pin.height(), width=driver_pin.lx() - pin_x)

    def route_write_driver_mask_in(self, word, mask_flop_out_via_y, mask_driver_in_via_y):
        driver_pin = self.get_write_driver_mask_in(word)
        self.add_layout_pin(f"mask_in_bar[{word}]", METAL4,
                            vector(driver_pin.lx(), self.data_bus_y),
                            height=driver_pin.by() - self.data_bus_y,
                            width=driver_pin.width())

    def route_write_driver_data(self, word, flop_pin, driver_pin, y_bend):
        """data flop dout to write driver in"""
        via_y = self.get_m2_m3_below_instance(self.write_driver_array_inst, 0)
        if "bar" in flop_pin.name:
            x_offset = flop_pin.cx()
            fill_alignment = RIGHT_FILL
        else:
            x_offset = driver_pin.cx()
            fill_alignment = LEFT_FILL
            self.add_rect(METAL2, vector(x_offset, flop_pin.uy() - self.m2_width),
                          width=flop_pin.cx() - x_offset, height=self.m2_width)
        y_offset = flop_pin.uy() - self.m2_width
        m2_rect = self.add_rect(METAL2, vector(x_offset - 0.5 * flop_pin.width(), y_offset),
                                width=flop_pin.width(), height=self.m2_width)
        m4_rect = self.add_rect(METAL4, vector(driver_pin.lx(), via_y),
                                width=driver_pin.width(), height=driver_pin.by() - via_y)
        self.join_rects([m4_rect], METAL4, [m2_rect], METAL2, fill_alignment,
                        rect_align=JOIN_BOT_ALIGN)

    def route_flops(self):
        self.route_all_instance_power(self.data_in_flops_inst)

        y_mid = self.get_data_flop_via_y()

        for word in range(self.word_size):
            brb_pin = self.write_driver_array_inst.get_pin(f"brb[{word}]")
            pin_x = brb_pin.cx() - 0.5 * self.m4_width
            flop_pin = self.data_in_flops_inst.get_pin(f"din[{word}]")
            rect = self.add_rect(METAL2, vector(flop_pin.lx(), y_mid),
                                 width=flop_pin.width(),
                                 height=flop_pin.by() - y_mid)
            self.add_contact_center(m2m3.layer_stack, vector(flop_pin.cx(), y_mid))
            data_pin = self.add_layout_pin(f"DATA[{word}]", METAL4,
                                           vector(pin_x, self.data_bus_y),
                                           height=y_mid - self.data_bus_y,
                                           width=self.m4_width)
            self.join_pins_with_m3(rect, data_pin, y_mid)
            self.add_contact_center(m3m4.layer_stack, vector(data_pin.cx(), y_mid))

    def get_wordline_vdd_offset(self):
        tap_x = self.wwl_driver.body_tap_insts[0].lx() + self.wwl_driver_inst.lx()
        return tap_x - self.wide_power_space - self.vdd_rail_width

    def join_wordline_power(self):
        self.wwl_driver.add_body_taps()
        WordlineVoltageMixin.route_wordline_power_pins(self, self.wwl_driver_inst)
        self.duplicate_m2_pin(self.get_pin("vdd_wordline"), "vdd",
                              self.wwl_driver_inst, m4_pin_name="vdd_wordline")

        x_offset = self.vdd_wordline.lx() - self.wide_power_space - self.vdd_rail_width
        gnd_rect = self.add_rect(METAL2, vector(x_offset, self.vdd_wordline.by()),
                                 width=self.vdd_rail_width,
                                 height=self.vdd_wordline.height())
        gnd_rect.layer = METAL2
        self.duplicate_m2_pin(gnd_rect, "gnd", self.rwl_driver_inst)
        for pin in (self.wwl_driver_inst.get_pins("gnd") +
                    self.rwl_driver_inst.get_pins("gnd")):
            x_offset = pin.lx() if pin.lx() > gnd_rect.cx() else pin.rx()
            self.add_rect(METAL1, vector(x_offset, pin.by()),
                          width=gnd_rect.cx() - x_offset, height=pin.height())
            self.add_power_via(pin, gnd_rect)

    def route_decoder_in(self):
        self.join_decoder_in()
        for row in range(self.num_rows):
            self.copy_layout_pin(self.decoder_logic_inst, f"in_0[{row}]", f"dec_in_0[{row}]")
            self.copy_layout_pin(self.decoder_logic_inst, f"in_1[{row}]", f"dec_in_1[{row}]")

    def route_wordline_in(self):
        left_inst, right_inst = sorted([self.wwl_driver_inst, self.rwl_driver_inst],
                                       key=lambda x: x.lx())
        for row in range(self.num_rows):
            logic_pin = self.decoder_logic_inst.get_pin(f"out[{row}]")
            driver_pin = left_inst.get_pin(f"in[{row}]")

            y_offset = logic_pin.uy() if row % 2 == 0 else logic_pin.by()
            self.add_rect(METAL2, vector(logic_pin.lx(), y_offset), width=logic_pin.width(),
                          height=driver_pin.cy() - y_offset)
            self.add_cross_contact_center(cross_m2m3, vector(logic_pin.cx(), driver_pin.cy()),
                                          rotate=False, fill=False)
            self.add_rect(METAL3, vector(logic_pin.cx(), driver_pin.by()),
                          height=driver_pin.height(),
                          width=driver_pin.cx() - logic_pin.cx())

    def get_dec_en_1_y(self):
        return self.get_decoder_enable_y() - 2 * self.bus_pitch + 0.5 * self.bus_width

    def route_decoder_enable(self):
        RwlWwlMixin.route_decoder_enable(self)
        BlBank.route_dec_en_1(self)

    def duplicate_m2_pin(self, m2_pin, inst_pin_name, inst, m4_pin_name=None):
        m4_pin_name = m4_pin_name or inst_pin_name
        width = m2_pin.rx() - m2_pin.lx()
        self.add_layout_pin(m4_pin_name, METAL4, offset=m2_pin.ll(), width=width,
                            height=m2_pin.uy() - m2_pin.by())

        fill_width = width
        fill_width, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL3)

        for pin in inst.get_pins(inst_pin_name):
            offset = vector(m2_pin.cx(), pin.cy())
            self.add_rect_center(METAL3, offset,
                                 width=fill_width, height=fill_height)
            for via in [m2m3, m3m4]:
                self.add_contact_center(via.layer_stack,
                                        offset=offset, size=[1, 2], rotate=90)

    def route_body_tap_supplies(self):
        self.decoder_logic.add_body_taps()
        self.copy_layout_pin(self.decoder_logic_inst, "gnd")
        self.route_intra_array_body_taps()

        x_offset = self.decoder_logic_vdd_offset
        pins = self.decoder_logic_inst.get_pins("vdd")
        bottom_y = min(pins, key=lambda x: x.by()).by()
        top_y = max(pins, key=lambda x: x.uy()).uy()
        rect = self.add_rect(METAL2, vector(x_offset, bottom_y), width=self.vdd_rail_width,
                             height=top_y - bottom_y)
        rect.layer = METAL2
        self.duplicate_m2_pin(rect, "vdd", self.decoder_logic_inst)
        for pin in (self.decoder_logic_inst.get_pins("vdd") +
                    self.wordline_driver_inst.get_pins("vdd")):
            self.add_power_via(pin, rect)
            rect_x = pin.rx() if pin.lx() < rect.lx() else pin.lx()
            rect_end = rect.rx() if pin.lx() < rect.lx() else rect.lx()
            self.add_rect(pin.layer, vector(rect_x, pin.by()),
                          width=rect_end - rect_x, height=pin.height())

    def get_right_vdd_offset(self):
        x_offset = super().get_right_vdd_offset()
        if getattr(OPTS, "buffer_repeaters_x_offset", None):
            wide_space = self.get_wide_space(METAL4)
            self.buffer_repeaters_x_offset = (self.bitcell_array_inst.rx() +
                                              self.bus_space + wide_space)
            num_rails = len(OPTS.buffer_repeater_sizes)
            rails_right = (self.buffer_repeaters_x_offset + num_rails * self.bus_width +
                           (num_rails - 1) * self.bus_space)
            x_offset = max(x_offset, rails_right + wide_space)
        return x_offset

    def route_control_buffer_repeaters(self):
        has_dedicated_space = OPTS.dedicated_repeater_space
        x_base = OPTS.buffer_repeaters_x_offset

        OPTS.dedicated_repeater_space = True
        OPTS.buffer_repeaters_x_offset = self.buffer_repeaters_x_offset

        super().route_control_buffer_repeaters()

        OPTS.dedicated_repeater_space = has_dedicated_space
        OPTS.buffer_repeaters_x_offset = x_base

    def calculate_bus_rail_width_spacing(self):
        bus_width = self.bus_width
        parallel_space = self.bus_space
        return bus_width, parallel_space, 0

    def connect_repeater_rail_to_dest(self, dest_pin, via_mid_x, bus_width):
        super().connect_repeater_rail_to_dest(dest_pin, via_mid_x, bus_width)
        right_x = via_mid_x + 0.5 * m3m4.h_1
        self.add_rect(dest_pin.layer, dest_pin.lr(), height=dest_pin.height(),
                      width=right_x - dest_pin.rx())

    def get_intra_array_grid_top(self):
        vdd_pin = self.precharge_array_inst.get_pins("vdd")[0]
        return vdd_pin.cy() + 0.5 * m3m4.h_2

    def calculate_mid_array_m4_x_offset(self):
        super().calculate_mid_array_m4_x_offset()
        m6m7 = contact(("metal6", "via6", "metal7"))
        self.intra_m4_rail_mid_x = utils.round_to_grid(0.5 * self.bitcell.width)
        self.max_intra_m4_rail_width = m6m7.w_1

        brb_pin = self.write_driver_array_inst.get_pin("brb[0]")
        blb_pin = self.write_driver_array_inst.get_pin("blb[0]")

        self.m4_grid_fill_width = (blb_pin.lx() - brb_pin.rx() -
                                   2 * self.get_parallel_space(METAL4))
        _, self.m4_grid_fill_height = self.calculate_min_area_fill(self.m4_grid_fill_width,
                                                                   layer=METAL4)

        self.m5_grid_fill_height = m4m5.h_2
        _, self.m5_grid_fill_width = self.calculate_min_area_fill(self.m5_grid_fill_height,
                                                                  layer=METAL5)

    def route_intra_array_body_taps(self):
        if not OPTS.use_x_body_taps:
            return

        all_power_pins = self.get_all_power_pins()

        for tap_inst in self.write_driver_array.tap_insts:
            for rail_name in ["vdd", "gnd"]:
                pin = tap_inst.get_pin(rail_name)
                offset = vector(pin.lx(), self.right_vdd.by())
                m4_rect = self.add_rect(METAL4, offset=offset, height=self.right_vdd.uy() - offset.y,
                                        width=pin.width())
                offset = vector(pin.lx(), self.data_bus_y)
                m6_pin = self.add_layout_pin(rail_name, "metal6", offset=offset,
                                             height=self.right_vdd.uy() - offset.y, width=pin.width())
                for inst_pin in all_power_pins:
                    if inst_pin.name == rail_name and inst_pin.layer == METAL3:
                        offset = vector(m4_rect.cx(), inst_pin.cy())
                        for via, rotate in zip([cross_m4m5, cross_m5m6], [False, True]):
                            self.add_cross_contact_center(via, offset, rotate=rotate, fill=False)
                        self.add_rect_center(METAL5, offset, width=self.m5_grid_fill_width,
                                             height=self.m5_grid_fill_height)
                self.connect_control_buffers_power_to_grid(m6_pin)

    def add_m4_grid_pin(self, pin_name, x_offset, min_point, rail_width, rail_top):
        return self.add_layout_pin(pin_name, "metal6",
                                   offset=vector(x_offset, min_point),
                                   width=rail_width, height=rail_top - min_point)

    def connect_m4_grid_instance_power(self, instance_pin, power_rail):
        if power_rail.lx() > instance_pin.lx() and power_rail.rx() < instance_pin.rx():
            offset = vector(power_rail.cx(), instance_pin.cy())
            for via, rotate in zip([cross_m3m4, cross_m4m5, cross_m5m6],
                                   [True, False, True]):
                self.add_cross_contact_center(via, offset, rotate=rotate, fill=False)
            self.add_rect_center(METAL4, offset, width=self.m4_grid_fill_width,
                                 height=self.m4_grid_fill_height)
            self.add_rect_center(METAL5, offset, width=self.m5_grid_fill_width,
                                 height=self.m5_grid_fill_height)

    def connect_control_buffers_power_to_grid(self, grid_pin):
        for control_pin in self.control_buffers_inst.get_pins(grid_pin.name):
            self.connect_m4_grid_instance_power(control_pin, grid_pin)
            continue
