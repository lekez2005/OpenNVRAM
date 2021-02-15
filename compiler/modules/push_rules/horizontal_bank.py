import debug
from base.contact import m2m3, m3m4, m1m2
from base.design import METAL2, METAL1, METAL3, METAL4
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import LEFT_FILL, RIGHT_FILL, BaselineBank
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.latched_control_logic import LatchedControlLogic
from modules.push_rules.pgate_horizontal import pgate_horizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap


class HorizontalBank(BaselineBank):
    rotation_for_drc = GDS_ROT_270

    def add_modules(self):
        super().add_modules()

    def add_pins(self):
        super().add_pins()
        self.add_pin("wordline_en")

    def create_control_buffers(self):
        self.control_buffers = LatchedControlLogic(self)
        self.add_mod(self.control_buffers)

    def create_control_flop(self):
        self.control_flop = self.create_module("flop_buffer", OPTS.control_flop,
                                               OPTS.control_flop_buffers, dummy_indices=[0])
        self.control_flop_neg = self.create_module("flop_buffer", OPTS.control_flop,
                                                   OPTS.control_flop_buffers,
                                                   dummy_indices=[0], negate=True)

    def get_control_flop_connections(self):
        connections = super().get_control_flop_connections()
        dict_keys = list(sorted(connections.keys(),
                                key=lambda x: self.get_control_buffer_net_pin(connections[x][1]).by()))
        # remove dummies from middle flops
        for i in range(1, len(dict_keys)):
            if i == len(dict_keys) - 1:
                if i % 2 == 1:
                    continue
                dummy_indices = [2]
            else:
                dummy_indices = []
            connection = connections[dict_keys[i]]
            original_flop = connection[2]
            flop_buffer = self.create_module("flop_buffer", OPTS.control_flop, OPTS.control_flop_buffers,
                                             dummy_indices=dummy_indices, negate=original_flop.negate)
            connections[dict_keys[i]] = (connection[0], connection[1], flop_buffer)
        return connections

    def get_right_vdd_offset(self):
        m2_extension = 0
        for module in [self.bitcell_array.bitcell, self.bitcell_array.body_tap]:
            right_m2 = max([x.rx() for x in module.get_layer_shapes(METAL2)])
            m2_extension = max(m2_extension, right_m2 - module.width)
        return max(self.bitcell_array_inst.rx() + m2_extension, self.rightmost_rail.rx(),
                   self.control_buffers_inst.rx()) + self.wide_m1_space

    def get_mid_gnd_offset(self):
        m2_extension = 0
        for module in [self.bitcell_array.bitcell, self.bitcell_array.body_tap]:
            left_m2 = min([x.lx() for x in module.get_layer_shapes(METAL2)])
            m2_extension = min(m2_extension, left_m2)
        return m2_extension - self.wide_m1_space - self.vdd_rail_width

    def get_row_decoder_control_flop_space(self):
        flop_vdd = self.control_flop.get_pins("vdd")[0]
        return flop_vdd.height() + 2 * self.poly_pitch  # prevent clash with poly dummies

    def get_precharge_y(self):
        if self.col_mux_array_inst is None:
            y_space = self.calculate_bitcell_aligned_spacing(self.precharge_array,
                                                             self.sense_amp_array)
            return self.sense_amp_array_inst.uy() + y_space
        return self.col_mux_array_inst.uy()

    def add_wordline_driver(self):
        x_offset = self.mid_vdd_offset - (self.wordline_driver.width + self.wide_m1_space)
        self.wordline_driver_inst = self.add_inst(name="wordline_buffer", mod=self.wordline_driver,
                                                  offset=vector(x_offset, self.bitcell_array_inst.by()))
        connections = self.get_wordline_driver_connections()
        connections.remove("wordline_en")
        self.connect_inst(connections)

    def route_bitcell_array_power(self):

        for pin in self.bitcell_array_inst.get_pins("vdd"):
            if pin.layer == METAL3 and pin.width() > pin.height():  # Horizontal M3 vdd
                self.route_vdd_pin(pin)

        for pin in self.bitcell_array_inst.get_pins("gnd"):
            self.add_rect(METAL3, offset=vector(self.mid_gnd.lx(), pin.by()),
                          width=self.right_gnd.rx() - self.mid_gnd.lx(),
                          height=pin.height())
            for rail in [self.mid_gnd, self.right_gnd]:
                self.add_power_via(pin, rail, via_size=[1, 2])

    def route_column_mux(self):
        debug.info(1, "Route column mux")
        if self.col_mux_array_inst is None:
            return
        for i in range(self.words_per_row):
            self.copy_layout_pin(self.col_mux_array_inst, "sel[{}]".format(i))

        self.route_all_instance_power(self.col_mux_array_inst)

        reference_pin = self.col_mux_array_inst.get_pin("bl_out[0]")
        bl_y_offset = reference_pin.by() - m3m4.height
        br_y_offset = bl_y_offset - self.get_parallel_space(METAL3) - m3m4.height

        pin_names = ["bl", "br"]
        y_offsets = [bl_y_offset, br_y_offset]
        via_alignments = [LEFT_FILL, RIGHT_FILL]

        for i in range(2):
            pin_name = pin_names[i]
            for j in range(2):
                indices = range(j, self.word_size, 2)
                mux_names = ["{}_out[{}]".format(pin_name, col) for col in indices]
                mux_pins = [self.col_mux_array_inst.get_pin(x) for x in mux_names]
                sense_names = ["{}[{}]".format(pin_name, col) for col in indices]
                sense_pins = [self.sense_amp_array_inst.get_pin(x) for x in sense_names]

                if j % 2 == 0:  # direct connection
                    self.join_rects(mux_pins, mux_pins[0].layer,
                                    sense_pins, sense_pins[0].layer,
                                    via_alignment=via_alignments[i])
                else:
                    sense_conn_rects = []
                    mux_conn_rects = []
                    # align mux and sense pin
                    for mux_pin, sense_pin in zip(mux_pins, sense_pins):
                        y_offset = y_offsets[i]
                        offset = vector(sense_pin.lx(), y_offset)
                        self.add_rect(METAL3, offset=offset,
                                      width=mux_pin.rx() - sense_pin.lx(),
                                      height=m3m4.height)
                        sense_conn_rects.append(self.add_rect(METAL3, offset=offset,
                                                              width=sense_pin.width(),
                                                              height=m3m4.height))
                        mux_conn_rects.append(self.add_rect(METAL3, offset=vector(mux_pin.lx(),
                                                                                  offset.y),
                                                            width=mux_pin.width(),
                                                            height=m3m4.height))
                    self.join_rects(sense_conn_rects, METAL3,
                                    sense_pins, sense_pins[0].layer,
                                    via_alignment=via_alignments[i])
                    self.join_rects(mux_pins, mux_pins[0].layer,
                                    mux_conn_rects, METAL3,
                                    via_alignment=via_alignments[i])

    def route_write_driver(self):
        """Route mask, data and data_bar from flops to write driver"""
        debug.info(1, "Route write driver")
        mask_flop_out_via_y = self.get_m2_m3_below_instance(self.data_in_flops_inst, 0)

        driver_pin = self.get_write_driver_mask_in(0)
        mask_driver_in_via_y = driver_pin.by()
        for word in range(0, self.word_size):
            self.route_write_driver_data_in(word)
            self.route_write_driver_data_bar_in(word)
            if self.has_mask_in:
                self.route_write_driver_mask_in(word, mask_flop_out_via_y,
                                                mask_driver_in_via_y)
        self.route_all_instance_power(self.write_driver_array_inst)

    def route_write_driver_data_bar_in(self, word):
        flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(word))
        driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(word))
        y_offset = flop_pin.uy() + self.get_line_end_space(METAL2)
        self.add_rect(METAL2, offset=flop_pin.ul(),
                      height=y_offset + self.m2_width - flop_pin.uy())
        self.add_rect(METAL2, offset=vector(flop_pin.lx(), y_offset),
                      width=driver_pin.lx() - flop_pin.lx())
        self.add_rect(METAL2, offset=vector(driver_pin.lx(), y_offset),
                      height=driver_pin.by() - y_offset)

    def route_write_driver_data_in(self, word):
        flop_pin = self.data_in_flops_inst.get_pin("dout[{}]".format(word))
        driver_pin = self.write_driver_array_inst.get_pin("data[{}]".format(word))
        self.add_contact(m2m3.layer_stack, offset=flop_pin.ul() - vector(0, m2m3.height))
        y_offset = flop_pin.uy() - self.m3_width
        self.add_rect(METAL3, offset=vector(flop_pin.lx(), y_offset),
                      width=max(self.m3_width, driver_pin.lx() - flop_pin.lx(), key=abs))
        self.add_rect(METAL3, offset=vector(driver_pin.lx(), y_offset),
                      height=driver_pin.by() - y_offset)
        self.add_contact(m2m3.layer_stack, offset=vector(driver_pin.lx(), driver_pin.by()))

    def get_write_driver_mask_in(self, word):
        return self.write_driver_array_inst.get_pin("mask[{}]".format(word))

    def get_mask_flop_out(self, word):
        return self.mask_in_flops_inst.get_pin("dout[{}]".format(word))

    def route_wordline_driver(self):
        if not self.is_left_bank:
            rail = getattr(self, "wordline_en_rail")
            self.add_layout_pin("wordline_en", METAL2, rail.ll(), width=rail.width, height=rail.height)
        for row in range(self.num_rows):
            self.copy_layout_pin(self.wordline_driver_inst, "decode[{}]".format(row),
                                 "dec_out[{}]".format(row))
        fill_width = self.mid_vdd.width()
        fill_width, fill_height = self.calculate_min_area_fill(fill_width, min_height=self.m2_width,
                                                               layer=METAL2)
        rails = [self.mid_vdd, self.mid_gnd]
        pin_names = ["vdd", "gnd"]
        for i in range(2):
            pin_name = pin_names[i]
            rail = rails[i]
            for pin in self.wordline_driver_inst.get_pins(pin_name):
                self.add_rect(pin.layer, offset=pin.lr(), height=pin.height(),
                              width=rail.rx() - pin.rx())
                self.add_contact_center(m2m3.layer_stack, offset=vector(rail.cx(), pin.cy()),
                                        size=[1, 2], rotate=90)
                self.add_rect_center(METAL2, offset=vector(rail.cx(), pin.cy()),
                                     width=fill_width, height=fill_height)

    def route_body_tap_supplies(self):
        pass

    def add_m2m4_power_rails_vias(self):
        all_power_pins = self.get_all_power_pins()

        for rail in [self.mid_vdd, self.right_vdd, self.mid_gnd, self.right_gnd]:
            y_offset = self.bitcell_array_inst.by() - m2m3.height
            self.add_rect(METAL1, offset=vector(rail.lx(), y_offset), width=rail.width(),
                          height=rail.uy() - y_offset)
            self.add_layout_pin(rail.name, METAL4, offset=rail.ll(), width=rail.width(),
                                height=rail.height())
            for pin in all_power_pins:
                if pin.cy() > self.precharge_array_inst.uy():
                    self.add_contact_center(m1m2.layer_stack, offset=vector(rail.cx(), pin.cy()),
                                            size=[1, 2], rotate=90)
                if pin.name == rail.name and pin.layer == METAL3:
                    # avoid bitcell conflict with right rail
                    if pin.cy() > self.precharge_array_inst.uy() and rail == self.right_vdd:
                        continue
                    self.add_contact_center(m3m4.layer_stack, offset=vector(rail.cx(), pin.cy()),
                                            size=[1, 2], rotate=90)

    def create_control_buffer_repeaters(self):
        super().create_control_buffer_repeaters()
        right_inst = max(self.repeaters_insts, key=lambda x: x.rx())
        body_tap = pgate_horizontal_tap(right_inst.mod.buffer_invs[-1])
        self.add_mod(body_tap)
        self.add_inst(body_tap.name, body_tap, offset=right_inst.lr())
        self.connect_inst([])

    def create_repeater(self, buffer_sizes):
        module = BufferStagesHorizontal(buffer_stages=buffer_sizes)
        self.add_mod(module)
        return module

    def get_repeater_height(self):
        return pgate_horizontal.height

    def get_repeater_input_via_x(self, in_pin):
        return in_pin.cx()

    def route_repeater_input(self, rail_rect, in_pin):
        if rail_rect.cy() > in_pin.cy():
            via_y = in_pin.uy() - 0.5 * m1m2.height
        else:
            via_y = in_pin.by() + 0.5 * m1m2.height
        self.add_rect(METAL2, offset=vector(in_pin.lx(), via_y),
                      height=rail_rect.cy() - via_y)
        self.add_contact_center(m1m2.layer_stack, offset=vector(in_pin.cx(), via_y))

    def route_repeater_output(self, output_nets, buffer_dict, min_rail_width):
        super().route_repeater_output(output_nets, buffer_dict, min_rail_width)
        for net in output_nets:
            output_pin = buffer_dict[net]
            output_rail = self.repeater_output_rails[net]
            if output_rail.by() > output_pin.cy():
                via_y = output_pin.uy() - 0.5 * m1m2.height
            else:
                via_y = output_pin.by() + 0.5 * m1m2.height
            self.add_contact_center(m1m2.layer_stack, offset=vector(output_pin.cx(), via_y))
