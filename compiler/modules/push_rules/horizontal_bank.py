from typing import List

import debug
from base.contact import m2m3, m3m4, m1m2
from base.design import METAL2, METAL1, METAL3, METAL4
from base.geometry import instance
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from base.well_implant_fills import well_implant_instance_fills
from globals import OPTS
from modules.baseline_bank import LEFT_FILL, RIGHT_FILL
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.latched_control_logic import LatchedControlLogic
from modules.push_rules.pgate_horizontal import pgate_horizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap
from modules.shared_decoder.cmos_bank import CmosBank


class HorizontalBank(CmosBank):
    rotation_for_drc = GDS_ROT_270

    def add_pins(self):
        super().add_pins()
        clk_buf_index = self.pins.index("clk_buf")
        self.pins = self.pins[:clk_buf_index]
        self.add_pin_list(["precharge_trig", "clk_buf", "clk_bar", "vdd", "gnd"])
        if not self.is_left_bank:
            self.add_pin("wordline_en")

    @staticmethod
    def get_module_list():
        return ["bitcell", "decoder", "ms_flop_array", "wordline_buffer",
                "bitcell_array", "sense_amp_array", "precharge_array",
                "write_driver_array", "tri_gate_array", "flop_buffer", "column_mux_array"]

    def create_modules(self):
        super().create_modules()
        self.wordline_buffer = self.create_module("wordline_buffer", rows=self.num_rows)

    def add_modules(self):
        super().add_modules()
        self.fill_modules()

    def connect_inst(self, args, check=True):
        current_inst_name = self.insts[-1].name
        if current_inst_name == "tri_gate_array":
            args.remove("tri_en_bar")
        elif current_inst_name == "write_driver_array":
            args = " ".join(args)
            args = args.replace("mask_in_bar", "mask_in").split()
            args.remove("write_en_bar")
        super().connect_inst(args, check)

    def create_control_buffers(self):
        self.control_buffers = LatchedControlLogic(is_left_bank=self.is_left_bank)
        self.add_mod(self.control_buffers)

    def create_control_flop(self):
        self.control_flop = self.create_module("flop_buffer", OPTS.control_flop,
                                               OPTS.control_flop_buffers, dummy_indices=[0])

    def connect_control_buffers(self):
        connections = ["bank_sel_buf", "read_buf", "clk", "sense_trig", "precharge_trig",
                       "clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                       "write_en", "sense_en", "tri_en", "sample_en_bar", "vdd", "gnd"]
        if self.is_left_bank:
            connections.remove("wordline_en")
        self.connect_inst(connections)

    def get_control_rails_destinations(self):
        destination_pins = {
            "sense_en": self.sense_amp_array_inst.get_pins("en"),
            "tri_en": self.tri_gate_array_inst.get_pins("en"),
            "sample_bar": self.sense_amp_array_inst.get_pins("sampleb"),
            "precharge_en_bar": (self.precharge_array_inst.get_pins("en")
                                 + self.sense_amp_array_inst.get_pins("preb")),
            "clk_buf": self.mask_in_flops_inst.get_pins("clk"),
            "clk_bar": self.data_in_flops_inst.get_pins("clk"),
            "write_en": self.write_driver_array_inst.get_pins("en"),
        }
        if not self.is_left_bank:  # differentiate left right
            destination_pins["wordline_en"] = self.precharge_array_inst.get_pins("en")
        return destination_pins

    def get_control_names(self):
        return ["sense_en", "tri_en", "sample_bar", "wordline_en",
                "precharge_en_bar", "clk_buf", "clk_bar", "write_en"]

    def get_right_vdd_offset(self):
        m2_extension = 0
        for module in [self.bitcell_array.bitcell, self.bitcell_array.body_tap]:
            right_m2 = max([x.rx() for x in module.get_layer_shapes(METAL2)])
            m2_extension = max(m2_extension, right_m2 - module.width)
        return max(self.bitcell_array_inst.rx() + m2_extension,
                   self.control_buffers_inst.rx()) + self.wide_m1_space

    def get_mid_gnd_offset(self):
        m2_extension = 0
        for module in [self.bitcell_array.bitcell, self.bitcell_array.body_tap]:
            left_m2 = min([x.lx() for x in module.get_layer_shapes(METAL2)])
            m2_extension = min(m2_extension, left_m2)
        return m2_extension - self.wide_m1_space - self.vdd_rail_width

    def get_control_logic_top(self, module_space):
        control_logic_top = super().get_control_logic_top(module_space)
        if self.is_left_bank:
            # add extra space for missing wordline_en_rail so both banks stay same height
            control_logic_top += self.bus_pitch
        return control_logic_top

    def get_row_decoder_control_flop_space(self):
        flop_vdd = self.control_flop.get_pins("vdd")[0]
        return flop_vdd.height() + 2 * self.poly_pitch  # prevent clash with poly dummies

    def get_non_flop_control_inputs(self):
        return ["sense_trig", "precharge_trig"]

    def get_module_y_space(self, bottom_instance, top_mod, num_horizontal_rails=0):
        top_modules = [top_mod.child_mod, top_mod.child_mod]
        bottom_modules = [bottom_instance.mod.child_mod, bottom_instance.mod.child_mod]
        if num_horizontal_rails > 0:
            layers = [METAL2, METAL3]
        else:
            layers = None
        y_space = self.evaluate_vertical_module_spacing(top_modules=top_modules,
                                                        bottom_modules=bottom_modules,
                                                        layers=layers)
        if num_horizontal_rails > 0:
            pitch = m2m3.height + self.get_parallel_space(METAL3)
            y_space += (self.get_line_end_space(METAL2) + m2m3.height +
                        max(0, num_horizontal_rails - 1) * pitch)

        return bottom_instance.uy() + y_space

    def get_mask_flops_y_offset(self):
        # above tri gate array
        return self.get_module_y_space(self.tri_gate_array_inst, self.msf_mask_in)

    def get_data_flops_y_offset(self):
        # above mask flops
        return self.get_module_y_space(self.mask_in_flops_inst, self.msf_data_in)

    def get_write_driver_offset(self):
        # above data flops
        y_offset = self.get_module_y_space(self.data_in_flops_inst, self.write_driver_array,
                                           num_horizontal_rails=1)
        return vector(self.data_in_flops_inst.lx(), y_offset)

    def get_sense_amp_array_y(self):
        return self.get_module_y_space(self.write_driver_array_inst, self.sense_amp_array)

    def get_precharge_mirror(self):
        return ""

    def get_column_mux_array_y(self):
        space = 2 * (self.m3_width + self.get_parallel_space(METAL3))
        return self.sense_amp_array_inst.uy() + space

    def get_precharge_y(self):
        if self.col_mux_array_inst is None:
            return self.get_module_y_space(self.sense_amp_array_inst, self.precharge_array)
        return self.col_mux_array_inst.uy()

    def add_wordline_driver(self):
        x_offset = self.mid_vdd_offset - (self.wordline_buffer.width + self.wide_m1_space)
        self.wordline_driver_inst = self.add_inst(name="wordline_buffer", mod=self.wordline_buffer,
                                                  offset=vector(x_offset, self.bitcell_array_inst.by()))
        connections = self.get_wordline_driver_connections()
        connections.remove("wordline_en")
        self.connect_inst(connections)

    def fill_vertical_space(self, bottom_reference_inst: instance, top_reference_inst: instance,
                            fill_instances: List[instance], y_space: float,
                            parent_top_inst: instance):
        """
        Fill space between two adjacent top bottom instances
        :param bottom_reference_inst: Reference bottom instance for computing fill rectangles
        :param top_reference_inst: Reference top instance
        :param fill_instances: Fills will be applied relative to the x-offset of each instance
        :param y_space: y space between top reference and bottom reference
        :param parent_top_inst: instance containing fill_instances
        """
        fill_rects = well_implant_instance_fills(bottom_reference_inst,
                                                 top_reference_inst)
        reference_x = parent_top_inst.lx()
        reference_y = parent_top_inst.by() - y_space - bottom_reference_inst.height

        for layer, x_offset, y_offset, width, height in fill_rects:
            for inst in fill_instances:
                self.add_rect(layer, vector(x_offset + (inst.lx() - top_reference_inst.lx())
                                            + reference_x,
                                            y_offset + reference_y),
                              width=width, height=height + y_space)

    def fill_modules(self):
        debug.info(1, "Filling space between modules")

        def fill_dual_mirror(bottom_inst, top_inst):
            """Fill between modules that are mirrored in groups of two"""
            debug.info(2, "Fill space between {} and {}".format(bottom_inst.name,
                                                                top_inst.name))
            y_space_ = top_inst.by() - bottom_inst.uy()
            debug.info(2, "y_space = {:.3g}".format(y_space_))
            self.fill_vertical_space(bottom_inst.mod.child_insts[0],
                                     top_inst.mod.child_insts[0],
                                     top_inst.mod.child_insts[::2], y_space_, top_inst)
            self.fill_vertical_space(bottom_inst.mod.child_insts[1],
                                     top_inst.mod.child_insts[1],
                                     top_inst.mod.child_insts[1::2], y_space_, top_inst)

        def fill_single_mirror(bottom_inst, top_inst, bottom_index, top_index, stride=4):
            """Fill between modules that are mirrored in groups of one"""
            self.fill_vertical_space(bottom_inst.mod.child_insts[bottom_index],
                                     top_inst.mod.child_insts[top_index],
                                     top_inst.mod.child_insts[top_index::stride],
                                     y_space, top_inst)

        fill_dual_mirror(self.tri_gate_array_inst, self.mask_in_flops_inst)
        fill_dual_mirror(self.mask_in_flops_inst, self.data_in_flops_inst)

        # data flop -> write driver
        debug.info(2, "Fill space between data flop and write driver")
        y_space = self.write_driver_array_inst.by() - self.data_in_flops_inst.uy()
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 0, 0)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 0, 1)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 1, 2)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 1, 3)

        # write_driver -> sense amp
        debug.info(2, "Fill space between write driver and sense amp")
        y_space = self.sense_amp_array_inst.by() - self.write_driver_array_inst.uy()
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 0, 0, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 1, 0, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 2, 1, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 3, 1, 2)

        # sense amp -> precharge
        debug.info(2, "Fill space between sense amp and precharge")
        y_space = self.precharge_array_inst.by() - self.sense_amp_array_inst.uy()
        if self.col_mux_array_inst is None:
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 0, 0)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 0, 1)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 1, 2)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 1, 3)

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

    def route_write_driver_data_bar(self, word):
        flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(word))
        driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(word))
        y_offset = flop_pin.uy() + self.get_line_end_space(METAL2)
        self.add_rect(METAL2, offset=flop_pin.ul(),
                      height=y_offset + self.m2_width - flop_pin.uy())
        self.add_rect(METAL2, offset=vector(flop_pin.lx(), y_offset),
                      width=driver_pin.lx() - flop_pin.lx())
        self.add_rect(METAL2, offset=vector(driver_pin.lx(), y_offset),
                      height=driver_pin.by() - y_offset)

    def route_write_driver_data(self, word):
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
        self.copy_layout_pin(self.control_buffers_inst, "wordline_en")
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
