import debug
from base.contact import m3m4, cross_m2m3, m2m3, cross_m1m2, cross_m3m4
from base.design import METAL3, METAL2, METAL4, design
from base.vector import vector
from modules.baseline_bank import BaselineBank, EXACT
from modules.bitline_compute.decoder_logic import DecoderLogic


class BlBank(BaselineBank):
    """
    Represents a bitline compute bank
    """

    def add_pins(self):
        """Add bank pins"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("mask_in_bar[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("and[{0}]".format(i))
            self.add_pin("nor[{0}]".format(i))
        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                self.add_pin("sel[{}]".format(i))
        for row in range(self.num_rows):
            self.add_pin(f"dec_in_0[{row}]")
            self.add_pin(f"dec_in_1[{row}]")

        diff_pins = ["diff", "diffb"] * (not self.mirror_sense_amp)
        control_pins = self.get_control_pins()
        if self.mirror_sense_amp and not "clk_pin" in control_pins:
            control_pins.append("clk_buf")
        self.add_pin_list(control_pins + diff_pins +
                          ["dec_en_1", "vdd", "gnd"])

    def get_control_rails_base_x(self):
        # space for vref
        return self.mid_vdd_offset - self.wide_m1_space - self.bus_pitch

    def get_control_pins(self):
        control_pins = super().get_control_pins()
        control_pins += ["vref"]
        return control_pins

    def create_modules(self):
        self.decoder_logic = DecoderLogic(num_rows=self.num_rows)
        self.add_mod(self.decoder_logic)
        super().create_modules()

    def derive_control_flops(self):
        combinations = super().derive_control_flops()
        combinations.append(("dec_en_1", False))
        return combinations

    def get_control_buffer_net_pin(self, net):
        if net == "dec_en_1_buf":
            # put above other control flops so use decoder enable pin
            return self.decoder_logic_inst.get_pin("en_1")
        return super().get_control_buffer_net_pin(net)

    def get_control_flop_connections(self):
        connections = super().get_control_flop_connections()
        connections["dec_en_1_buf"] = ("dec_en_1", "dec_en_1_buf",
                                       self.control_flop_mods["dec_en_1"])
        return connections

    def validate_control_flop_name(self, inst_name, inst):
        if inst_name == "dec_en_1_buf":
            self.dec_en_1_buf_inst = inst
            return
        super().validate_control_flop_name(inst_name, inst)

    def get_non_flop_control_inputs(self):
        return ["sense_trig"] * (not self.mirror_sense_amp)

    def add_tri_gate_array(self):
        self.tri_gate_array_inst = None

    def add_mask_flops(self):
        self.has_mask_in = False
        self.mask_in_flops_inst = None

    def get_data_flops_y_offset(self, flop=None, flop_tap=None):
        return self.trigate_y + m2m3.height  # for via to data layout pin

    def get_data_flop_via_y(self):
        return self.get_m2_m3_below_instance(self.data_in_flops_inst, 0)

    def get_custom_net_destination(self, net):
        if net == "clk_buf":
            return []
        return super().get_custom_net_destination(net)

    def add_wordline_driver(self):
        super().add_wordline_driver()
        self.add_decoder_logic()

    def get_decoder_logic_x(self):
        return self.wordline_driver_inst.lx() - self.decoder_logic.width

    def add_decoder_logic(self):
        x_offset = self.get_decoder_logic_x()
        y_offset = self.wordline_driver_inst.by()
        self.decoder_logic_inst = self.add_inst(self.decoder_logic.name, mod=self.decoder_logic,
                                                offset=vector(x_offset, y_offset))
        connections = self.connections_from_mod(self.decoder_logic, [
            ("in_0[", "dec_in_0["), ("in_1[", "dec_in_1["),
            ("out[", "dec_out["), ("en_1", "dec_en_1_buf", EXACT)
        ])
        self.connect_inst(connections)

    def route_control_flop_outputs(self):
        control_flop_insts = self.control_flop_insts
        self.control_flop_insts = [x for x in control_flop_insts
                                   if not x[2] == self.dec_en_1_buf_inst]
        x_offset = super().route_control_flop_outputs()
        self.control_flop_insts = control_flop_insts
        return x_offset

    def get_sense_amp_array_connections(self):
        connections = super().get_sense_amp_array_connections()
        connections = self.connections_from_mod(connections,
                                                [("precharge_en_bar", "sense_precharge_bar")])
        return connections

    def route_sense_amp(self):
        """Routes sense amp power and connects write driver bitlines to sense amp bitlines"""
        debug.info(1, "Route sense amp")
        self.route_all_instance_power(self.sense_amp_array_inst)

        self.data_bus_y = self.control_buffers_inst.by()

        sense_amp = self.sense_amp_array_inst.mod.child_mod
        m3 = min(sense_amp.get_layer_shapes(METAL3, recursive=True), key=lambda x: x.by())
        via_y = min(0, m3.by() - m3m4.height - self.get_parallel_space(METAL3))

        # write driver to sense amp
        self.join_bitlines(top_instance=self.sense_amp_array_inst, top_suffix="",
                           bottom_instance=self.write_driver_array_inst,
                           bottom_suffix="", y_shift=via_y)
        self.route_sense_amp_vref()
        self.route_and_nor_pins()
        if not self.mirror_sense_amp:
            self.route_sense_diff_pins()

    def route_sense_amp_vref(self):
        # add vref
        ref_pins = self.sense_amp_array_inst.get_pins("vref")
        top_pin = max(ref_pins, key=lambda x: x.uy()).cy()
        x_offset = self.mid_vdd.lx() - self.wide_m1_space - self.bus_width
        vref_pin = self.add_layout_pin("vref", METAL2, vector(x_offset, self.data_bus_y),
                                       width=self.bus_width, height=top_pin - self.data_bus_y)
        for pin in ref_pins:
            self.add_cross_contact_center(cross_m2m3, offset=vector(vref_pin.cx(), pin.cy()))
            self.add_rect(METAL3, offset=vector(x_offset, pin.by()), height=pin.height(),
                          width=pin.lx() - x_offset)

    def route_sense_diff_pins(self):
        diff_pins = self.sense_amp_array_inst.get_pins("diff")
        diffb_pins = self.sense_amp_array_inst.get_pins("diffb")
        lowest_diff = min(diff_pins + diffb_pins, key=lambda x: x.by())

        x_offsets = []
        control_names = [x for x in self.left_control_rails if x not in ["decoder_clk"]]
        left_rails = [getattr(self, f"{rail_name}_rail") for rail_name in control_names]
        left_rails = sorted(left_rails, key=lambda x: x.lx(), reverse=True)
        for rail in left_rails:
            if rail.uy() < lowest_diff.by():
                x_offsets.append(rail.lx())
            if len(x_offsets) == 2:
                break
        pin_names = ["diff", "diffb"]
        for i, pins in enumerate([diff_pins, diffb_pins]):
            x_offset = x_offsets[i]
            m3_x_offset = x_offset + 0.5 * self.bus_width - 0.5 * m2m3.h_2
            for pin in pins:
                self.add_rect(METAL3, vector(m3_x_offset, pin.by()), height=pin.height(),
                              width=pin.lx() - m3_x_offset)
                design.add_cross_contact_center(self, cross_m2m3,
                                                vector(x_offset + 0.5 * self.bus_width, pin.cy()))

            bottom, top = sorted(pins, key=lambda x: x.by())
            y_offset = bottom.cy() - 0.5 * m2m3.height
            self.add_layout_pin(pin_names[i], METAL2,
                                vector(x_offset, y_offset), width=self.bus_width,
                                height=top.cy() + 0.5 * m2m3.height - y_offset)

    def route_and_nor_pins(self):
        for pin_name in ["and", "nor"]:
            for word in range(self.word_size):
                full_name = f"{pin_name}[{word}]"
                pin = self.sense_amp_array_inst.get_pin(full_name)
                self.add_layout_pin(full_name, METAL4, vector(pin.lx(), self.data_bus_y),
                                    width=pin.width(), height=pin.by() - self.data_bus_y)

    def route_write_driver(self):
        self.has_mask_in = True
        super().route_write_driver()
        self.has_mask_in = False

    def get_mask_flop_via_y(self):
        return None

    def route_data_flop_in(self, bitline_pins, word, data_via_y, fill_width, fill_height,
                           pin_name="bl"):
        # use the bl pin
        super().route_data_flop_in(bitline_pins, word, data_via_y, fill_width, fill_height,
                                   pin_name=pin_name)

    def route_write_driver_mask_in(self, word, mask_flop_out_via_y, mask_driver_in_via_y):
        via_y = mask_driver_in_via_y
        driver_pin = self.get_write_driver_mask_in(word)
        # align with sense amp bitline
        br_pin = self.sense_amp_array_inst.get_pin("br[{}]".format(word))
        br_x_offset = br_pin.lx()
        self.add_rect(METAL2, offset=vector(driver_pin.lx(), via_y),
                      width=driver_pin.width(), height=driver_pin.by() - via_y)
        via_offset = vector(driver_pin.cx() - 0.5 * m2m3.width, via_y)
        cont1 = self.add_contact(m2m3.layer_stack, via_offset)
        via_offset = vector(br_x_offset, via_y + 0.5 * m2m3.second_layer_height -
                            0.5 * m3m4.height)
        cont2 = self.add_contact(m3m4.layer_stack, offset=via_offset)

        self.join_pins_with_m3(cont1, cont2, cont1.cy(), fill_height=m3m4.first_layer_height)

        self.add_layout_pin(f"mask_in_bar[{word}]", METAL4, vector(br_x_offset, self.data_bus_y),
                            height=via_y - self.data_bus_y, width=br_pin.width())

    def route_flops(self):
        min_point = self.min_point
        self.min_point = self.data_bus_y
        super().route_flops()
        self.min_point = min_point

    def route_wordline_enable(self):
        super().route_wordline_enable()
        self.route_dec_en_1()

    def get_dec_en_1_y(self):
        return self.get_decoder_enable_y() - self.bus_pitch

    def route_dec_en_1(self):
        # route dec_en_1
        flop_pin = self.dec_en_1_buf_inst.get_pin("dout")
        m2_rails = [x for x in self.m2_rails if x.uy() > flop_pin.uy() - self.bus_pitch]
        leftmost_rail = min(m2_rails, key=lambda x: x.lx())

        y_offset = self.dec_en_1_buf_inst.uy() + 0.5 * self.rail_height + self.parallel_line_space
        x_offset = leftmost_rail.lx() - self.bus_pitch

        # flop output to m2 rail x
        self.add_rect(METAL2, flop_pin.ul(), width=flop_pin.width(),
                      height=y_offset + self.bus_width - flop_pin.uy())
        via_y = y_offset + 0.5 * self.bus_width
        self.add_cross_contact_center(cross_m2m3, vector(flop_pin.cx(), via_y))
        self.add_rect(METAL3, vector(x_offset, y_offset), width=flop_pin.cx() - x_offset,
                      height=self.bus_width)
        self.add_cross_contact_center(cross_m2m3, vector(x_offset +
                                                         0.5 * self.bus_width, via_y))

        enable_y = self.get_dec_en_1_y()
        # create m2 rail
        rail = self.add_rect(METAL2, vector(x_offset, y_offset), width=self.bus_width,
                             height=enable_y - y_offset)
        self.m2_rails.append(rail)
        self.leftmost_rail = rail
        self.decoder_enable_rail = rail
        # m2 rail to enable input
        dec_pin = self.decoder_logic_inst.get_pin("en_1")
        self.add_cross_contact_center(cross_m2m3, vector(rail.cx(), enable_y))
        self.add_rect(METAL3, vector(dec_pin.cx(), enable_y - 0.5 * self.bus_width),
                      height=self.bus_width, width=rail.cx() - dec_pin.cx())

        mid_y = enable_y + self.bus_pitch

        self.add_contact_center(m2m3.layer_stack, vector(dec_pin.cx(), mid_y),
                                rotate=90)
        self.add_rect(METAL3, vector(dec_pin.lx(), mid_y), width=dec_pin.width(),
                      height=enable_y - 0.5 * self.bus_width - mid_y)
        self.add_rect(METAL2, vector(dec_pin.lx(), mid_y), width=dec_pin.width(),
                      height=dec_pin.by() - enable_y)

    def route_wordline_in(self):
        fill_width = m2m3.height
        _, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL2)
        for row in range(self.num_rows):
            self.copy_layout_pin(self.decoder_logic_inst, f"in_0[{row}]", f"dec_in_0[{row}]")
            self.copy_layout_pin(self.decoder_logic_inst, f"in_1[{row}]", f"dec_in_1[{row}]")

            in_0_pin = self.decoder_logic_inst.get_pin(f"in_0[{row}]")
            out_pin = self.decoder_logic_inst.get_pin(f"out[{row}]")
            in_pin = self.wordline_driver_inst.get_pin(f"in[{row}]")

            self.add_rect(METAL2, out_pin.ul(), height=in_0_pin.by() - out_pin.uy(),
                          width=out_pin.width())
            design.add_cross_contact_center(self, cross_m2m3, vector(out_pin.cx(), in_0_pin.cy()))
            self.add_rect(METAL3, vector(out_pin.cx(), in_0_pin.by()),
                          width=in_pin.cx() - out_pin.cx() + 0.5 * self.m3_width,
                          height=in_0_pin.height())
            self.add_rect(METAL3, vector(in_pin.cx() - 0.5 * self.m3_width, in_pin.cy()),
                          width=self.m3_width, height=in_0_pin.cy() - in_pin.cy())
            self.add_contact_center(m2m3.layer_stack, in_pin.center())
            design.add_cross_contact_center(self, cross_m1m2, in_pin.center(), rotate=True)
            if fill_height:
                self.add_rect_center(METAL2, in_pin.center(), width=fill_width,
                                     height=fill_height)

    def route_intra_array_power_grid(self):
        min_point = self.min_point
        self.min_point = self.data_bus_y
        super().route_intra_array_power_grid()
        self.min_point = min_point

    def connect_m4_grid_instance_power(self, instance_pin, power_rail):
        if power_rail.lx() > instance_pin.lx() and power_rail.rx() < instance_pin.rx():
            design.add_cross_contact_center(self, cross_m3m4,
                                            offset=vector(power_rail.cx(), instance_pin.cy()),
                                            rotate=True)
