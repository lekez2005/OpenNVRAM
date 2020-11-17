from base import utils
from base.contact import m2m3, m3m4, m1m2, contact, cross_m2m3, cross_m1m2
from base.design import PIMP, NIMP, METAL1, METAL2, METAL3, METAL4
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import BaselineBank
from modules.buffer_stage import BufferStage
from tech import drc


class CmosBank(BaselineBank):

    def calculate_dimensions(self):
        self.width = self.bitcell_array_inst.rx() - self.wordline_driver_inst.lx()
        self.height = self.bitcell_array_inst.uy() - self.control_buffers_inst.by()

    def create_modules(self):
        super().create_modules()
        if self.col_addr_size > 0:
            self.column_mux_array = self.create_module('column_mux_array', word_size=self.word_size,
                                                       columns=self.num_cols)

    def add_modules(self):
        self.add_control_buffers()
        self.add_tri_gate_array()
        self.add_data_mask_flops()
        self.add_write_driver_array()
        self.add_sense_amp_array()
        self.add_column_mux_array()
        self.add_precharge_array()
        self.add_bitcell_array()
        self.add_wordline_driver()
        self.add_control_rails()

        self.min_point = min(map(lambda x: x.by(), self.objs))
        self.min_point = min(self.min_point, min(map(lambda x: x.by(), self.insts)))

        if self.num_banks > 1:
            # space for joining read, clk, sense_trig
            space = self.get_wide_space(METAL3)
            self.min_point -= (space + 3 * self.m3_pitch)
        self.top = self.bitcell_array_inst.uy()

        self.add_control_flops()

        self.add_vdd_gnd_rails()

    def route_layout(self):

        self.route_control_buffer()
        self.route_control_flops()
        return
        self.route_precharge()
        self.route_column_mux()
        self.route_sense_amp()
        self.route_bitcell()
        self.route_write_driver()
        self.route_flops()
        self.route_tri_gate()
        self.route_wordline_driver()

        if hasattr(OPTS, "right_buffers_x_actual"):
            self.create_control_buffer_repeaters()
            self.route_control_buffer_repeaters()

        self.calculate_rail_vias()  # horizontal rail vias
        self.add_decoder_power_vias()
        self.add_right_rails_vias()
        self.route_body_tap_supplies()
        self.route_control_buffers_power()

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))
        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                self.add_pin("sel[{}]".format(i))
        for i in range(self.num_rows):
            self.add_pin("dec_out[{}]".format(i))

        self.add_pin_list(["bank_sel", "read", "clk", "sense_trig",
                           "clk_buf", "clk_bar", "vdd", "gnd"])

    def create_control_buffers(self):
        if OPTS.baseline:
            if self.words_per_row == 1:

                from modules.baseline_latched_control_buffers import LatchedControlBuffers
            else:
                from modules.shared_decoder.cmos_baseline_control_buffers import LatchedControlBuffers
        else:
            from modules.bitline_compute.bl_latched_control_buffers import LatchedControlBuffers
        self.control_buffers = LatchedControlBuffers()
        self.add_mod(self.control_buffers)

    def add_control_buffers(self):
        offset = vector(0, self.logic_buffers_bottom)
        self.control_buffers_inst = self.add_inst("control_buffers", mod=self.control_buffers,
                                                  offset=offset)
        self.connect_control_buffers()

    def connect_control_buffers(self):
        self.connect_inst(["bank_sel_buf", "read_buf", "clk", "sense_trig", "clk_buf", "clk_bar",
                           "wordline_en", "precharge_en_bar", "write_en", "write_en_bar",
                           "sense_en", "tri_en", "tri_en_bar", "sample_en_bar", "vdd", "gnd"])

    def get_collisions(self):
        collisions = [
            (self.control_buffers_inst.by(), self.tri_gate_array_inst.by()),
            (self.tri_gate_array_inst.get_pin("en").uy(),
             self.tri_gate_array_inst.get_pin("en_bar").uy()),
        ]
        if self.words_per_row > 1:
            # space for sel rails
            collisions.append((self.col_mux_array_inst.get_pin("sel[{}]".format(self.words_per_row - 1)).by(),
                               self.col_mux_array_inst.get_pin("sel[0]").uy()))
            wide_space = self.get_wide_space(METAL2)
            top_y = self.wordline_driver_inst.by() - wide_space
            bottom_y = top_y - (1 + self.words_per_row) * self.m3_pitch
            self.col_decoder_rail_space = (1 + self.words_per_row) * self.m3_pitch + wide_space
            collisions.append((bottom_y, top_y))
        if self.num_banks > 1:  # space for control rails from left bank to right  bank
            collisions.append((self.min_point, self.min_point + 3 * self.m3_pitch))
        return collisions

    def get_mask_flops_y_offset(self):
        # above tri gate array
        top_modules = [self.msf_mask_in.ms, self.msf_mask_in.body_tap]
        bottom_modules = [self.tri_gate_array.tri, self.tri_gate_array.body_tap]

        y_space = self.evaluate_vertical_module_spacing(top_modules=top_modules,
                                                        bottom_modules=bottom_modules)
        y_offset = self.tri_gate_array_inst.uy() + y_space
        return y_offset

    def get_precharge_y(self):
        if self.col_mux_array_inst is None:
            precharge_nimplant = max(self.precharge_array.pc_cell.get_layer_shapes(NIMP),
                                     key=lambda x: x.uy())
            nimp_extension = precharge_nimplant.uy() - self.precharge_array.pc_cell.height
            sense_amp_pimplant = max(self.sense_amp_array.amp.
                                     get_layer_shapes(PIMP, recursive=True),
                                     key=lambda x: x.uy())
            pimp_extension = sense_amp_pimplant.uy() - self.sense_amp_array.amp.height
            space = nimp_extension + pimp_extension
            return self.sense_amp_array_inst.uy() + self.precharge_array.height + space
        else:
            return self.col_mux_array_inst.uy() + self.precharge_array.height

    def get_data_flops_y_offset(self):
        # above mask flops
        bottom_modules = [self.msf_mask_in.ms, self.msf_mask_in.body_tap]
        top_modules = [self.msf_data_in.ms, self.msf_data_in.body_tap]

        y_space = self.evaluate_vertical_module_spacing(top_modules=top_modules,
                                                        bottom_modules=bottom_modules)
        y_offset = self.mask_in_flops_inst.uy() + y_space
        return y_offset

    def add_control_flops(self):
        x_offset, y_offset = self.get_control_flops_offset()

        self.bank_sel_buf_inst = self.add_inst("bank_sel_buf", mod=self.control_flop,
                                               offset=vector(x_offset, y_offset))
        self.connect_inst(["bank_sel", "clk", "bank_sel_buf", "vdd", "gnd"])

        offset = self.bank_sel_buf_inst.ul() + vector(0, self.control_flop.height)
        self.read_buf_inst = self.add_inst("read_buf", mod=self.control_flop, offset=offset, mirror="MX")
        self.connect_inst(["read", "clk", "read_buf", "vdd", "gnd"])

    def get_control_flops_offset(self):
        # add to the left of the leftmost control rail
        wide_space = self.get_wide_space(METAL1)
        y_offset = self.control_buffers_inst.by()
        x_offset = (self.leftmost_rail.offset.x - 2 * self.m2_pitch -
                    wide_space - self.control_flop.width)
        return x_offset, y_offset

    def add_column_mux_array(self):
        if self.col_addr_size == 0:
            self.col_mux_array_inst = None
            return

        y_offset = self.sense_amp_array_inst.uy()
        self.col_mux_array_inst = self.add_inst(name="column_mux_array", mod=self.column_mux_array,
                                                offset=vector(self.sense_amp_array_inst.lx(), y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        for k in range(self.words_per_row):
            temp.append("sel[{0}]".format(k))
        for j in range(self.word_size):
            temp.append("bl_out[{0}]".format(j))
            temp.append("br_out[{0}]".format(j))
        temp.append("gnd")
        if "vdd" in self.column_mux_array.pins:
            temp.append("vdd")
        self.connect_inst(temp)

    def get_right_vdd_offset(self):
        return max(self.bitcell_array_inst.rx(),
                   self.control_buffers_inst.rx()) + self.wide_m1_space

    def route_control_buffer(self):
        # copy vdd, gnd and clk outputs
        self.copy_layout_pin(self.control_buffers_inst, "clk_buf")
        self.copy_layout_pin(self.control_buffers_inst, "clk_bar")

        for vdd_pin in self.control_buffers_inst.get_pins("vdd"):
            self.route_vdd_pin(vdd_pin)
        for gnd_pin in self.control_buffers_inst.get_pins("gnd"):
            self.route_gnd_pin(gnd_pin)

        wide_space = self.get_wide_space(METAL1)

        # outputs of control flops for read and bank_sel to control buffers inputs
        rail_height = self.bus_width
        instances = [self.bank_sel_buf_inst, self.read_buf_inst]
        control_pins = ["bank_sel", "read"]

        x_offset = self.read_buf_inst.rx() + wide_space
        _, fill_height = self.calculate_min_m1_area(rail_height, layer=METAL2)
        for i in range(2):
            mid_x = x_offset + 0.5 * rail_height
            control_pin = self.control_buffers_inst.get_pin(control_pins[i])
            flop_pin = instances[i].get_pin("dout")

            if flop_pin.by() + 0.5 * rail_height <= control_pin.cy() <= \
                    flop_pin.uy() - 0.5 * rail_height:
                y_offset = control_pin.cy()
            elif flop_pin.uy() <= control_pin.cy():
                y_offset = flop_pin.uy() - 0.5 * rail_height
            else:
                y_offset = flop_pin.by() + 0.5 * rail_height

            self.add_rect(METAL1, offset=vector(flop_pin.lx(), y_offset - 0.5 * rail_height),
                          width=mid_x - flop_pin.lx(), height=rail_height)
            self.add_cross_contact_center(cross_m1m2, offset=vector(mid_x, y_offset),
                                          rotate=True)

            self.add_rect(METAL2, offset=vector(mid_x - 0.5 * rail_height, y_offset),
                          width=rail_height,
                          height=max(fill_height, control_pin.cy() - y_offset, key=abs))
            self.add_cross_contact_center(cross_m2m3, offset=vector(mid_x, control_pin.cy()),
                                          rotate=False)
            m3_height = min(rail_height, control_pin.height())
            self.add_rect(METAL3, offset=vector(x_offset, control_pin.cy() - 0.5 * m3_height),
                          height=m3_height, width=control_pin.lx() - x_offset)

            x_offset += self.bus_pitch

        control_pins = [self.control_buffers_inst.get_pin(x) for x in
                        self.get_non_flop_control_inputs()]
        control_pins = list(sorted(control_pins, key=lambda x: x.by()))
        for pin in control_pins:
            self.add_layout_pin(pin.name, METAL2, offset=vector(x_offset, self.min_point),
                                width=rail_height, height=pin.cy() - self.min_point)
            self.add_cross_contact_center(cross_m2m3,
                                          offset=vector(x_offset + 0.5 * rail_height,
                                                        pin.cy()))
            m3_height = min(rail_height, pin.height())
            self.add_rect(METAL3, offset=vector(x_offset, pin.cy() - 0.5 * m3_height),
                          width=pin.lx() - x_offset, height=m3_height)
            x_offset += self.bus_pitch

    def get_non_flop_control_inputs(self):
        """Get control buffers inputs that don't go through flops"""
        return ["sense_trig"]

    def route_control_flops(self):
        # vdd gnd
        source_pins = [self.bank_sel_buf_inst.get_pin("gnd"), self.bank_sel_buf_inst.get_pin("vdd"),
                       self.read_buf_inst.get_pin("gnd")]
        dest_pins = [self.control_buffers_inst.get_pin("gnd"),
                     self.control_buffers_inst.get_pin("vdd"),
                     self.tri_gate_array_inst.get_pin("gnd")]
        for i in range(3):
            source_pin = source_pins[i]
            dest_pin = dest_pins[i]
            bend_x = 0.5 * (source_pin.rx() + dest_pin.lx())
            self.add_rect(METAL1, offset=source_pin.lr(), width=bend_x + source_pin.height() - source_pin.rx(),
                          height=source_pin.height())
            self.add_rect(METAL1, offset=vector(bend_x, source_pin.by()), width=source_pin.height(),
                          height=dest_pin.cy() - source_pin.by())
            self.add_rect(METAL1, offset=vector(bend_x, dest_pin.by()), height=dest_pin.height(),
                          width=dest_pin.lx() - bend_x)

        wide_space = self.get_wide_space(METAL1)

        # input pins
        min_height = self.metal1_minwidth_fill
        # bank_sel in
        x_offset = self.bank_sel_buf_inst.lx() - wide_space - self.m2_width
        in_pin = self.bank_sel_buf_inst.get_pin("din")
        self.add_layout_pin("bank_sel", METAL2, offset=vector(x_offset, self.min_point),
                            height=max(min_height, in_pin.uy() - self.min_point))
        self.add_rect(METAL2, offset=vector(x_offset, in_pin.by()), width=in_pin.lx() - x_offset)

        # pass clk along vdd to minimize risk of m3 clash
        x_offset -= self.m2_pitch
        vdd_pin = self.bank_sel_buf_inst.get_pin("vdd")
        clk_pin = self.get_pin("clk")
        self.add_rect(METAL2, offset=clk_pin.ul(), height=vdd_pin.cy() - clk_pin.uy())
        self.add_rect(METAL3, offset=vector(x_offset, vdd_pin.cy() - 0.5 * self.m3_width),
                      width=clk_pin.rx() - x_offset)
        self.add_contact_center(m2m3.layer_stack, offset=vector(clk_pin.cx(), vdd_pin.cy()))

        clk_top = self.read_buf_inst.get_pin("clk")
        clk_bottom = self.bank_sel_buf_inst.get_pin("clk")
        self.add_rect(METAL2, offset=vector(x_offset, clk_bottom.by()),
                      height=clk_top.uy() - clk_bottom.by())
        via_x = x_offset + 0.5 * m2m3.width
        self.add_contact_center(m2m3.layer_stack, offset=vector(via_x, vdd_pin.cy()))
        for pin in [clk_bottom, clk_top]:
            self.add_contact_center(m1m2.layer_stack, offset=vector(via_x, pin.cy()))
            self.add_rect(METAL1, offset=vector(x_offset, pin.by()), width=pin.lx() - x_offset)

        # read input
        x_offset -= self.m2_pitch
        read_in = self.read_buf_inst.get_pin("din")
        self.add_layout_pin("read", METAL2, offset=vector(x_offset, self.min_point),
                            height=read_in.uy() - self.min_point)
        self.add_rect(METAL2, offset=vector(x_offset, read_in.by()), width=read_in.lx() - x_offset)

    def route_precharge(self):
        super().route_precharge()
        if self.col_mux_array_inst is None:
            bottom_module = self.sense_amp_array_inst
        else:
            bottom_module = self.col_mux_array_inst
        for col in range(self.num_cols):
            # route bitlines
            for pin_name in ["bl", "br"]:
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name + "[{}]".format(col))
                bottom_pin = bottom_module.get_pin(pin_name + "[{}]".format(col))
                precharge_pin = self.precharge_array_inst.get_pin(pin_name + "[{}]".format(col))

                self.add_rect("metal4", offset=bottom_pin.ul(), height=precharge_pin.uy() - bottom_pin.uy())
                m2_m4_via_pins = [precharge_pin]
                if self.col_mux_array_inst is not None:
                    m2_m4_via_pins.append(bottom_pin)
                    if col % self.words_per_row == 0:
                        bit = int(col / self.words_per_row)
                        m2_m4_via_pins.append(self.sense_amp_array_inst.get_pin(pin_name + "[{}]".format(bit)))

                for m2_m4_via_pin in m2_m4_via_pins:
                    offset = m2_m4_via_pin.ul() - vector(0, m2m3.second_layer_height)

                    self.add_contact(m2m3.layer_stack, offset=offset)
                    self.add_contact(m3m4.layer_stack, offset=offset)
                    via_extension = drc["min_wide_metal_via_extension"]
                    if pin_name == "bl":
                        x_offset = bitcell_pin.lx() - via_extension
                    else:
                        x_offset = bitcell_pin.rx() - self.fill_width + via_extension
                    self.add_rect("metal3", offset=vector(x_offset, m2_m4_via_pin.uy() - self.fill_height),
                                  width=self.fill_width, height=self.fill_height)

    def route_column_mux(self):
        if self.col_mux_array_inst is None:
            return
        for i in range(self.words_per_row):
            self.copy_layout_pin(self.col_mux_array_inst, "sel[{}]".format(i))

        for pin in self.col_mux_array_inst.get_pins("vdd"):
            self.route_vdd_pin(pin)
        for pin in self.col_mux_array_inst.get_pins("gnd"):
            self.route_gnd_pin(pin)

    def route_sense_amp(self):
        dummy_contact = contact(m1m2.layer_stack, dimensions=[2, 1])

        pin_list = self.sense_amp_array.pin_map.values()
        all_pins = [item for sublist in pin_list for item in sublist]

        for pin in (self.sense_amp_array_inst.get_pins("gnd") +
                    self.sense_amp_array_inst.get_pins("vdd")):
            clash_top = False
            clash_bot = False
            collision_top = pin.cy() + 0.5 * dummy_contact.width + self.get_parallel_space(METAL1)
            collision_bot = pin.cy() - 0.5 * dummy_contact.width - self.get_parallel_space(METAL1)
            for candidate_pin in all_pins:
                if candidate_pin.name == pin.name or not candidate_pin.layer == METAL1:
                    continue
                if collision_top > candidate_pin.by() + self.sense_amp_array_inst.by() > pin.uy():
                    clash_top = True
                if collision_bot < candidate_pin.uy() + self.sense_amp_array_inst.by() < pin.by():
                    clash_bot = True
            if clash_top:
                via_y = pin.uy() - dummy_contact.width
            elif clash_bot:
                via_y = pin.by()
            else:
                via_y = pin.cy() - 0.5 * dummy_contact.width
            if pin.name == "gnd":
                self.route_gnd_pin(pin, add_via=False)
                via_rails = [self.mid_gnd]
            else:
                self.route_vdd_pin(pin, add_via=False)
                via_rails = [self.right_vdd, self.mid_vdd]

            for via_rail in via_rails:
                via_offset = vector(via_rail.cx() + 0.5 * dummy_contact.height, via_y)
                self.add_contact(m1m2.layer_stack, size=[2, 1], offset=via_offset,
                                 rotate=90)

    def route_flops(self):
        # add din and mask in pins
        pin_names = ["MASK", "DATA"]
        modules = [self.mask_in_flops_inst, self.data_in_flops_inst]

        for j in range(2):
            module = modules[j]
            for pin in module.get_pins("gnd"):
                self.route_gnd_pin(pin, via_rotate=90)
            for pin in module.get_pins("vdd"):
                self.route_vdd_pin(pin)

            pin_name = pin_names[j]
            for i in range(self.word_size):
                din_pin = module.get_pin("din[{}]".format(i))
                offset = vector(din_pin.cx(), din_pin.by())
                self.add_contact_center(m2m3.layer_stack, offset=offset)
                self.add_rect_center("metal3", offset=offset, width=self.fill_width,
                                     height=self.fill_height)
                if pin_name == "DATA":
                    x_offset = din_pin.lx()
                    self.add_contact(m3m4.layer_stack, offset=vector(x_offset, din_pin.by() -
                                                                     0.5 * m3m4.height))
                else:
                    x_offset = din_pin.cx() + 0.5 * self.fill_width + self.wide_m1_space
                    y_offset = din_pin.by() - 0.5 * self.fill_height

                    self.add_rect("metal3", offset=vector(din_pin.cx(), y_offset),
                                  width=x_offset - din_pin.cx())
                    self.add_contact_center(m3m4.layer_stack, offset=vector(x_offset + 0.5 * m3m4.width,
                                                                            y_offset + 0.5 * self.m3_width))
                self.add_layout_pin(text=pin_name + "[{}]".format(i), layer="metal4",
                                    offset=vector(x_offset, self.min_point),
                                    height=din_pin.by() - self.min_point)

    def route_tri_gate(self):
        self.route_vdd_pin(self.tri_gate_array_inst.get_pin("vdd"))
        self.route_gnd_pin(self.tri_gate_array_inst.get_pin("gnd"))

        for col in range(self.word_size):
            # route tri-gate output to data in pin
            data_pin = self.get_pin("DATA[{}]".format(col))
            tri_gate_out = self.tri_gate_array_inst.get_pin("out[{}]".format(col))

            offset = vector(data_pin.cx(), tri_gate_out.by() + m2m3.height)

            self.add_contact_center(m2m3.layer_stack, offset=offset)
            self.add_contact_center(m3m4.layer_stack, offset=offset)
            self.add_rect_center("metal3", offset=offset, width=self.fill_width,
                                 height=self.fill_height)
            self.add_rect("metal2", offset=offset - vector(0, 0.5 * self.m2_width),
                          width=tri_gate_out.cx() - offset.x)

            # route from sense amp to tri state in

            # place to the right of mask pin
            mask_pin = self.get_pin("MASK[{}]".format(col))
            tri_gate_in = self.tri_gate_array_inst.get_pin("in[{}]".format(col))
            x_offset = mask_pin.rx() + self.wide_m1_space

            offset = vector(x_offset + 0.5 * self.m4_width, tri_gate_in.uy())

            self.add_contact_center(m2m3.layer_stack, offset=offset)
            self.add_contact_center(m3m4.layer_stack, offset=offset)
            self.add_rect_center("metal3", offset=offset, width=self.fill_width,
                                 height=self.fill_height)
            self.add_rect("metal2", offset=vector(tri_gate_in.lx(), offset.y - 0.5 * self.m2_width),
                          width=offset.x - tri_gate_in.lx())

            # add bend in middle of write driver
            y_bend = 0.5 * (self.write_driver_array_inst.by() + self.write_driver_array_inst.uy())
            self.add_rect("metal4", offset=vector(x_offset, offset.y), height=y_bend - offset.y)

            sense_amp_out = self.sense_amp_array_inst.get_pin("data[{}]".format(col))
            bend_offset = vector(sense_amp_out.lx(), y_bend)
            self.add_rect("metal4", offset=bend_offset, width=x_offset + self.m4_width - bend_offset.x)
            self.add_rect("metal4", offset=bend_offset, height=sense_amp_out.by() - bend_offset.y)

    def route_wordline_driver(self):
        self.row_decoder_inst = self.wordline_driver_inst
        super().route_wordline_driver()
        for i in range(self.num_rows):
            self.copy_layout_pin(self.wordline_driver_inst, "in[{0}]".format(i),
                                 "dec_out[{0}]".format(i))
        self.row_decoder_inst = None

    def add_decoder_power_vias(self):
        self.vdd_grid_rects = []
        self.gnd_grid_rects = []

        for i in range(len(self.power_grid_vias)):
            via_y_offset = self.power_grid_vias[i]
            if i % 2 == 0:  # vdd
                # add vias to top
                via_x = self.mid_vdd.lx()
                self.add_inst(self.m2mtop.name, self.m2mtop,
                              offset=vector(via_x + 0.5 * self.vdd_rail_width, via_y_offset))
                self.connect_inst([])
                # connect rails horizontally
                self.vdd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(via_x, via_y_offset),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - via_x))
            else:  # gnd
                via_x = self.mid_gnd.lx() + 0.5 * self.vdd_rail_width
                self.add_inst(self.m2mtop.name, self.m2mtop,
                              offset=vector(via_x, self.power_grid_vias[i]))
                self.connect_inst([])
                self.gnd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(self.mid_gnd.lx(), self.power_grid_vias[i]),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - self.mid_gnd.lx()))

    def route_control_buffers_power(self):
        read_buf_inst = self.read_buf_inst
        self.read_buf_inst = self.control_buffers_inst
        super().route_control_buffers_power()
        self.read_buf_inst = read_buf_inst

    def add_vdd_gnd_rails(self):
        self.height = self.top - self.min_point

        right_vdd_offset = self.get_right_vdd_offset()
        right_gnd_offset = right_vdd_offset + self.vdd_rail_width + self.wide_m1_space

        offsets = [self.mid_gnd_offset, right_gnd_offset, self.mid_vdd_offset, right_vdd_offset]
        pin_names = ["gnd", "gnd", "vdd", "vdd"]
        pin_layers = self.get_vdd_gnd_rail_layers()[:4]

        attribute_names = ["mid_gnd", "right_gnd", "mid_vdd", "right_vdd"]
        for i in range(4):
            pin = self.add_layout_pin(pin_names[i], pin_layers[i],
                                      vector(offsets[i], self.min_point), height=self.height,
                                      width=self.vdd_rail_width)
            setattr(self, attribute_names[i], pin)
        # for IDE assistance
        self.mid_gnd = getattr(self, "mid_gnd")
        self.right_gnd = getattr(self, "right_gnd")
        self.mid_vdd = getattr(self, "mid_vdd")
        self.right_vdd = getattr(self, "right_vdd")

    def create_control_buffer_repeaters(self):

        self.buffer_dict = {}

        module_defs = getattr(OPTS, "right_buffers", [])

        module_height = self.control_buffers.logic_heights

        min_rail_width = utils.ceil(self.get_fill_width() ** 2 / self.m3_width)

        modules_x_offset = OPTS.right_buffers_x_actual - min_rail_width

        y_offset = self.control_buffers_inst.uy() - module_height

        module_defs = list(sorted(module_defs,
                                  key=lambda x: self.control_buffers_inst.get_pin(x[0]).cx()))

        buffer_dict = self.buffer_dict

        # create the modules
        modules = []
        for i in range(len(module_defs)):
            module_def = module_defs[i]
            buffer_sizes = module_def[2]
            module = BufferStage(buffer_stages=buffer_sizes, height=module_height, route_outputs=False)
            self.add_mod(module)
            modules.append(module)

            modules_x_offset -= module.width

        self.min_right_buffer_x = modules_x_offset

        for i in range(len(module_defs)):
            module_def = module_defs[i]
            module = modules[i]

            input_rail_net = module_def[0]
            output_nets = module_def[1]

            if len(buffer_sizes) % 2 == 0:
                output_terms = output_nets if len(output_nets) == 2 else \
                    [input_rail_net + "_buffer_dummy", input_rail_net]
            else:
                output_terms = output_nets if len(output_nets) == 2 else \
                    [input_rail_net, input_rail_net + "_buffer_dummy"]

            module_inst = self.add_inst("right_buffer_{}".format(input_rail_net), mod=module,
                                        offset=vector(modules_x_offset, y_offset))

            self.connect_inst([input_rail_net] + output_terms + ["vdd", "gnd"])

            buffer_dict[output_nets[-1]] = module_inst.get_pin("out")
            if len(output_nets) == 2:
                buffer_dict[output_nets[0]] = module_inst.get_pin("out_inv")

            # connect input rail
            input_rail = getattr(self, input_rail_net + "_rail")
            original_buffer_pin = self.control_buffers_inst.get_pin(input_rail_net)
            in_pin = module_inst.get_pin("in")
            x_offset = in_pin.lx() - m1m2.height

            self.add_rect("metal3", offset=vector(original_buffer_pin.lx(), input_rail.by()),
                          width=x_offset - original_buffer_pin.lx())

            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, input_rail.by()),
                             rotate=90)
            self.add_rect("metal2", offset=vector(x_offset - self.m2_width, in_pin.by()),
                          height=input_rail.by() + self.m2_width - in_pin.by())
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset + m1m2.height, in_pin.by()), rotate=90)

            # create output rails
            for net in output_nets:
                output_pin = buffer_dict[net]
                output_rail = getattr(self, net + "_rail")
                self.add_rect("metal2", offset=output_pin.ul(), height=output_rail.by() - output_pin.uy())
                self.add_rect("metal3", offset=vector(output_pin.lx(), output_rail.by()), width=min_rail_width)
                self.add_label(net, "metal3", vector(output_pin.lx(), output_rail.by()))
                self.add_contact(m2m3.layer_stack, offset=vector(output_pin.cx() + 0.5 * m2m3.height, output_rail.by()),
                                 rotate=90)

            modules_x_offset = module_inst.rx()

        self.max_right_buffer_x = modules_x_offset

    def route_control_buffer_repeaters(self):
        # maximize spacing between the rails
        # first check if opening is large enough to accommodate wide spacing
        available_space = OPTS.right_buffers_num_taps * self.bitcell_array.body_tap.width
        num_rails = len(self.buffer_dict.keys())
        side_space = self.get_wide_space(METAL4)
        parallel_space = self.get_parallel_space(METAL4)

        # find side space
        total_space = 2 * side_space + num_rails * self.m4_width + (num_rails - 1) * parallel_space

        if total_space > available_space:
            side_space = parallel_space

        # find parallel space
        total_intra_space = available_space - num_rails * self.m4_width - 2 * side_space
        parallel_space = max(parallel_space, utils.floor(total_intra_space / (num_rails - 1)))

        output_nets = self.buffer_dict.keys()
        sorted_output_nets = list(reversed(sorted(output_nets,
                                                  key=lambda net: getattr(self, net + "_rail").by())))

        destination_pins = self.get_control_rails_destinations()

        x_offset = OPTS.right_buffers_x_actual + side_space
        min_fill_x = x_offset - 0.5 * self.m4_width
        max_fill_x = (x_offset + num_rails * self.m4_width + (num_rails - 1) * parallel_space +
                      0.5 * self.m4_width)

        for output_net in sorted_output_nets:
            source_pin = self.buffer_dict[output_net]
            net_rail = getattr(self, output_net + "_rail")

            self.add_rect(METAL3, offset=vector(source_pin.lx(), net_rail.by()),
                          width=x_offset - source_pin.lx())

            self.add_contact(m3m4.layer_stack, offset=vector(x_offset, net_rail.by()))

            # find offsets for fills
            fill_width = self.fill_width
            fill_height = self.fill_height
            fill_x = x_offset + 0.5 * self.m4_width - 0.5 * fill_width
            fill_x = min(max(fill_x, min_fill_x), max_fill_x)

            all_destination_pins = [x for y in destination_pins.values() for x in y]
            fill_allowance = 0.5 * fill_height + parallel_space

            for dest_pin in destination_pins[output_net]:
                self.add_rect(METAL4, offset=vector(x_offset, net_rail.by()),
                              height=dest_pin.uy() - net_rail.by())
                # check if clashes with another
                clash = None
                for candidate in all_destination_pins:
                    if candidate.cy() == dest_pin.cy():
                        continue
                    if dest_pin.cy() > candidate.cy() and (dest_pin.cy() - candidate.uy() < fill_allowance):
                        clash = "below"
                    if dest_pin.cy() < candidate.cy() and (candidate.by() - dest_pin.cy() < fill_allowance):
                        clash = "above"

                if clash is None:
                    via_y = dest_pin.cy()
                elif clash == "below":
                    via_y = dest_pin.uy() + 0.5 * m2m3.height
                else:
                    via_y = dest_pin.by() - 0.5 * m2m3.height

                via_offset = vector(x_offset + 0.5 * self.m4_width, via_y)
                if dest_pin.layer == METAL3:
                    self.add_contact_center(m3m4.layer_stack, offset=via_offset)
                else:
                    if dest_pin.layer == METAL2:
                        self.add_contact_center(m3m4.layer_stack, offset=via_offset)
                        self.add_contact_center(m2m3.layer_stack, offset=via_offset, rotate=90)
                        fill_layers = [METAL3]
                        if clash is not None:
                            fill_layers.append(METAL2)
                    else:
                        self.add_contact_center(m1m2.layer_stack, offset=via_offset, rotate=90)
                        self.add_contact_center(m2m3.layer_stack, offset=via_offset)
                        self.add_contact_center(m3m4.layer_stack, offset=via_offset)
                        fill_layers = [METAL2, METAL3]
                        if clash is not None:
                            fill_layers.append(METAL1)

                    for layer in fill_layers:
                        self.add_rect(layer, offset=vector(fill_x, via_y - 0.5 * fill_height),
                                      width=fill_width, height=fill_height)

            x_offset += parallel_space + self.m4_width
