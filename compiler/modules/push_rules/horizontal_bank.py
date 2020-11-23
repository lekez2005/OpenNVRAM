from typing import List

import debug
from base import utils
from base.contact import cross_m2m3, m2m3, m3m4, m1m2, contact
from base.design import METAL2, METAL1, METAL3, METAL4
from base.geometry import instance
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from base.well_implant_fills import well_implant_instance_fills
from globals import OPTS
from modules.push_rules.latched_control_logic import LatchedControlLogic
from modules.shared_decoder.cmos_bank import CmosBank


class HorizontalBank(CmosBank):
    rotation_for_drc = GDS_ROT_270

    def __init__(self, word_size, num_words, words_per_row, num_banks=1, name="",
                 adjacent_bank=None):
        """For left bank, no buffer is instantiated for wordline_en"""
        self.is_left_bank = adjacent_bank is not None
        self.adjacent_bank = adjacent_bank

        super().__init__(word_size, num_words, words_per_row, num_banks, name)

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

    def get_vdd_gnd_rail_layers(self):
        return [METAL2] * 6

    def create_modules(self):
        if self.is_left_bank:
            for module_name in ["bitcell_array", "sense_amp_array", "precharge_array",
                                "write_driver_array", "tri_gate_array", "control_flop",
                                "msf_mask_in", "msf_data_in", "wordline_buffer", "decoder",
                                "bitcell"]:
                adjacent_mod = getattr(self.adjacent_bank, module_name)
                setattr(self, module_name, adjacent_mod)
                self.add_mod(adjacent_mod)
            self.create_control_buffers()
        else:
            super().create_modules()
            self.wordline_buffer = self.create_module("wordline_buffer", rows=self.num_rows)

    def route_layout(self):
        super().route_layout()
        self.route_intra_array_power_grid()

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
        return max(self.bitcell_array_inst.rx(),
                   self.control_buffers_inst.rx()) + m2_extension + self.wide_m1_space

    def get_mid_gnd_offset(self):
        m2_extension = 0
        for module in [self.bitcell_array.bitcell, self.bitcell_array.body_tap]:
            left_m2 = min([x.lx() for x in module.get_layer_shapes(METAL2)])
            m2_extension = min(m2_extension, left_m2)
        return m2_extension - self.wide_m1_space - self.vdd_rail_width

    def calculate_rail_offsets(self):
        super().calculate_rail_offsets()

        self.control_rail_pitch = self.bus_pitch

        control_outputs = self.get_control_names()
        control_outputs = [x for x in control_outputs if x in self.control_buffers.pins]

        control_outputs = list(sorted(control_outputs,
                                      key=lambda x: self.control_buffers.get_pin(x).lx()))
        # separate into top and bottom pins
        top_pins, bottom_pins = [], []
        for pin_name in control_outputs:
            pin = self.control_buffers.get_pin(pin_name)
            if pin.cy() > 0.5 * self.control_buffers.height:
                top_pins.append(pin_name)
            else:
                bottom_pins.append(pin_name)

        control_vdd = self.control_buffers.get_pins("vdd")[0]
        module_space = 0.5 * control_vdd.height() + self.m3_space

        if len(bottom_pins) > 0:
            self.logic_buffers_bottom = ((len(bottom_pins) * self.bus_pitch)
                                         - self.bus_space + module_space)
        else:
            self.logic_buffers_bottom = 0

        control_logic_top = (self.logic_buffers_bottom + self.control_buffers.height
                             + module_space)
        if self.is_left_bank:
            # add extra space for missing wordline_en_rail so both banks stay same height
            control_logic_top += self.bus_pitch
        self.trigate_y = (control_logic_top + (len(top_pins) * self.bus_pitch)) + self.get_line_end_space(METAL2)
        self.control_rail_offsets = {}

        for i in range(len(top_pins)):
            self.control_rail_offsets[top_pins[i]] = control_logic_top + i * self.bus_pitch

        y_offset = 0
        for i in reversed(range(len(bottom_pins))):
            self.control_rail_offsets[bottom_pins[i]] = y_offset
            y_offset += self.bus_pitch

        self.top_control_rails, self.bottom_control_rails = top_pins, bottom_pins

    def add_control_rails(self):
        destination_pins = self.get_control_rails_destinations()
        num_rails = len(destination_pins.keys())
        x_offset = (self.mid_vdd_offset - (num_rails * self.control_rail_pitch)
                    - (self.wide_m1_space - self.line_end_space))
        rail_names = list(sorted(destination_pins.keys(),
                                 key=lambda x: (-self.control_buffers_inst.get_pin(x).by(),
                                                self.control_rail_offsets[x]),
                                 reverse=False))
        self.rail_names = rail_names
        for rail_name in rail_names:
            self.add_control_rail(rail_name, destination_pins[rail_name],
                                  x_offset, self.control_rail_offsets[rail_name])
            x_offset += self.control_rail_pitch

        self.leftmost_rail = getattr(self, rail_names[0] + "_rail")
        if not self.is_left_bank:
            wordline_en_rail = getattr(self, "wordline_en_rail")
            self.add_layout_pin("wordline_en", METAL2, offset=wordline_en_rail.ll(),
                                width=wordline_en_rail.width, height=wordline_en_rail.height)

    def get_control_flops_offset(self):
        wide_space = self.get_wide_space(METAL2)
        # place to the left of bottom rail
        leftmost_bottom_rail_x = min(map(lambda x: getattr(self, x + "_rail").lx(),
                                         self.bottom_control_rails))

        num_control_inputs = len(self.get_non_flop_control_inputs())
        num_flop_inputs = 2
        num_inputs = num_control_inputs + num_flop_inputs + 1
        self.bank_sel_rail_x = (leftmost_bottom_rail_x - num_inputs * self.bus_pitch
                                - self.bus_space + wide_space)
        x_offset = (self.bank_sel_rail_x - wide_space
                    - self.control_flop.width)
        # place below predecoder
        flop_vdd = self.control_flop.get_pins("vdd")[0]
        row_decoder_flop_space = flop_vdd.height() + 2 * self.poly_pitch
        space = utils.ceil(1.2 * self.bus_space)
        row_decoder_col_decoder_space = flop_vdd.height() + 2 * space + self.bus_width

        # y offset based on control buffer
        y_offset_control_buffer = self.control_buffers_inst.cy() - self.control_flop.height

        row_decoder_y = self.bitcell_array_inst.uy() - self.decoder.height - self.bitcell.height
        y_offset = row_decoder_y - row_decoder_flop_space - 2 * self.control_flop.height

        # check if we can squeeze column decoder between predecoder and control flops
        self.col_decoder_is_left = False
        if self.words_per_row > 1:
            if self.words_per_row == 2:
                col_decoder_height = self.control_flop.height
            elif self.words_per_row == 4:
                col_decoder_height = self.decoder.pre2_4.height
            else:
                col_decoder_height = self.decoder.pre3_8.height

            rail_space_above_controls = row_decoder_flop_space + (1 + self.words_per_row) * self.bus_pitch

            if row_decoder_y - row_decoder_col_decoder_space - col_decoder_height - row_decoder_col_decoder_space > \
                    y_offset_control_buffer + 2 * self.control_flop.height:
                # predecoder is above control flops
                y_offset = y_offset_control_buffer
                self.col_decoder_y = row_decoder_y - row_decoder_col_decoder_space - col_decoder_height
            elif row_decoder_y - row_decoder_col_decoder_space - col_decoder_height > \
                    (y_offset_control_buffer + 2 * self.control_flop.height + rail_space_above_controls):
                # predecoder is still above control flops but move control flops down
                # if predecoder had been moved left, the rails above the control flops would have still
                # required moving control flops down anyway
                y_offset = (row_decoder_y - row_decoder_col_decoder_space - col_decoder_height -
                            rail_space_above_controls - 2 * self.control_flop.height)
                self.col_decoder_y = y_offset + 2 * self.control_flop.height + rail_space_above_controls
            else:
                # predecoder will be moved left
                self.col_decoder_is_left = True
                y_offset = (row_decoder_y - row_decoder_flop_space - rail_space_above_controls
                            - 2 * self.control_flop.height)
                self.col_decoder_y = row_decoder_y - row_decoder_col_decoder_space - col_decoder_height
                self.rail_space_above_controls = rail_space_above_controls
            self.min_point = min(self.min_point, self.col_decoder_y - self.rail_height)

        # place close to control_buffers
        y_offset = min(y_offset, self.control_buffers_inst.cy() - self.control_flop.height)
        # ensure no clash with rails above control_buffer
        top_rails = [getattr(self, x + "_rail") for x in self.top_control_rails]
        leftmost_top_rail = min(top_rails, key=lambda x: x.lx())
        if y_offset + 2 * self.control_flop.height > leftmost_top_rail.by() - wide_space:
            x_offset = leftmost_top_rail.by() - wide_space - 2 * self.control_flop.height

        self.control_flop_y = y_offset
        return x_offset, y_offset

    def get_non_flop_control_inputs(self):
        return ["sense_trig", "precharge_trig"]

    def get_module_y_space(self, bottom_instance, top_mod):
        top_modules = [top_mod.child_mod, top_mod.child_mod]
        bottom_modules = [bottom_instance.mod.child_mod, bottom_instance.mod.child_mod]
        y_space = self.evaluate_vertical_module_spacing(top_modules=top_modules,
                                                        bottom_modules=bottom_modules)
        return bottom_instance.uy() + y_space

    def get_mask_flops_y_offset(self):
        # above tri gate array
        return self.get_module_y_space(self.tri_gate_array_inst, self.msf_mask_in)

    def get_data_flops_y_offset(self):
        # above mask flops
        return self.get_module_y_space(self.mask_in_flops_inst, self.msf_data_in)

    def get_write_driver_offset(self):
        # above data flops
        y_offset = self.get_module_y_space(self.data_in_flops_inst, self.write_driver_array)
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
        args = ["dec_out[{}]".format(x) for x in range(self.num_rows)]
        args += ["wl[{}]".format(x) for x in range(self.num_rows)]
        self.connect_inst(args + ["vdd", "gnd"])

    def add_control_flops(self):
        super().add_control_flops()
        y_offset = (self.bank_sel_buf_inst.by() - self.get_wide_space(METAL2)
                    - self.bus_pitch)
        self.cross_clk_rail_y = y_offset
        self.min_point = min(self.min_point, self.cross_clk_rail_y)

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

    def route_control_flops(self):
        # vdd and gnd
        bottom_gnd, top_gnd = sorted(self.control_buffers_inst.get_pins("gnd"),
                                     key=lambda x: x.cy())
        y_offsets = [top_gnd.cy(), 0.5 * (bottom_gnd.cy() + top_gnd.cy()), bottom_gnd.cy()]
        destination_pins = [self.mid_gnd, self.mid_vdd, self.mid_gnd]
        pins = [self.read_buf_inst.get_pin("gnd"),
                self.bank_sel_buf_inst.get_pin("vdd"),
                self.bank_sel_buf_inst.get_pin("gnd")]
        x_start = self.get_pin("precharge_trig").lx()
        pitch = bottom_gnd.height() + self.get_wide_space(METAL1)
        for i in range(3):
            start_pin = pins[i]
            destination_y = y_offsets[i]
            x_offset = x_start + i * pitch
            self.add_rect(METAL1, offset=start_pin.lr(),
                          width=x_offset - start_pin.rx() + start_pin.height(),
                          height=start_pin.height())
            if abs(destination_y - start_pin.cy()) > self.m1_width:
                self.add_rect(METAL1, offset=vector(x_offset, start_pin.cy()),
                              width=start_pin.height(), height=destination_y - start_pin.cy())
            destination_pin = destination_pins[i]
            rect = self.add_rect(METAL1, offset=vector(x_offset,
                                                       destination_y - 0.5 * start_pin.height()),
                                 width=destination_pin.rx() - x_offset,
                                 height=start_pin.height())
            if i == 1:
                self.add_power_via(rect, self.mid_vdd)
        # clk, read, bank_sel
        instances = ([self.bank_sel_buf_inst], [self.read_buf_inst],
                     [self.bank_sel_buf_inst, self.read_buf_inst])
        pin_names = ["bank_sel", "read", "clk"]
        input_pin_names = ["din", "din", "clk"]
        x_base = (self.bank_sel_buf_inst.lx() - self.get_wide_space(METAL2)
                  - 3 * self.bus_pitch + self.bus_space)
        for i in range(3):
            x_offset = x_base + i * self.bus_pitch
            in_pin_name = input_pin_names[i]
            input_pins = [x.get_pin(in_pin_name) for x in instances[i]]
            top_pin = max(input_pins, key=lambda x: x.cy())
            self.add_layout_pin(pin_names[i], METAL2, offset=vector(x_offset, self.min_point),
                                width=self.bus_width,
                                height=top_pin.cy() - self.min_point)
            for input_pin in input_pins:
                if i > 0:
                    layer = METAL2
                else:
                    layer = METAL3
                    self.add_cross_contact_center(cross_m2m3,
                                                  offset=vector(x_offset + 0.5 * self.bus_width,
                                                                input_pin.cy()))
                    self.add_cross_contact_center(cross_m2m3,
                                                  offset=vector(input_pin.lx() + 0.5 * self.bus_width,
                                                                input_pin.cy()))
                self.add_rect(layer, offset=vector(x_offset, input_pin.by()),
                              width=input_pin.lx() - x_offset, height=input_pin.height())
        # clk to control_buffer
        clk_pin = self.get_pin("clk")
        rail_x = self.get_pin("sense_trig").lx() + self.bus_pitch
        y_offset = self.cross_clk_rail_y
        self.add_cross_contact_center(cross_m2m3, offset=vector(clk_pin.cx(),
                                                                y_offset + 0.5 * self.bus_width))
        self.add_rect(METAL3, offset=vector(clk_pin.cx(), y_offset),
                      width=rail_x - clk_pin.cx(), height=self.bus_width)
        self.add_cross_contact_center(cross_m2m3, offset=vector(rail_x + 0.5 * self.bus_width,
                                                                y_offset + 0.5 * self.bus_width))
        control_pin = self.control_buffers_inst.get_pin("clk")
        self.add_rect(METAL2, offset=vector(rail_x, y_offset), width=self.bus_width,
                      height=control_pin.cy() - y_offset)
        self.add_cross_contact_center(cross_m2m3, offset=vector(rail_x + 0.5 * self.bus_width,
                                                                control_pin.cy()))
        m3_height = min(self.bus_width, control_pin.height())
        self.add_rect(METAL3, offset=vector(rail_x, control_pin.cy() - 0.5 * m3_height),
                      width=control_pin.lx() - rail_x, height=m3_height)

    def route_all_power(self, inst, via_rotate=0):
        for pin in inst.get_pins("vdd"):
            self.route_vdd_pin(pin, via_rotate=via_rotate)

        for pin in inst.get_pins("gnd"):
            self.route_gnd_pin(pin, via_rotate=via_rotate)
            self.add_power_via(pin, self.right_gnd, via_rotate)

    def route_sense_amp(self):
        self.connect_sense_amp_bitlines()
        self.route_all_power(self.sense_amp_array_inst)

    def route_bitcell(self):
        for row in range(self.num_rows):
            wl_in = self.bitcell_array_inst.get_pin("wl[{}]".format(row))
            driver_out = self.wordline_driver_inst.get_pin("wl[{0}]".format(row))
            self.add_rect(METAL3, offset=vector(driver_out.rx(), wl_in.by()),
                          width=wl_in.lx() - driver_out.rx(), height=wl_in.height())

        for pin in self.bitcell_array_inst.get_pins("vdd"):
            if pin.layer == METAL3 and pin.width() > pin.height():  # Horizontal M3 vdd
                self.route_vdd_pin(pin)

        for pin in self.bitcell_array_inst.get_pins("gnd"):
            self.add_rect(METAL3, offset=vector(self.mid_gnd.lx(), pin.by()),
                          width=self.right_gnd.rx() - self.mid_gnd.lx(),
                          height=pin.height())
            for rail in [self.mid_gnd, self.right_gnd]:
                self.add_power_via(pin, rail, via_size=[1, 2])

    def route_write_driver(self):

        for col in range(0, self.word_size):
            fill_width = self.medium_m3
            fill_width, fill_height = self.calculate_min_m1_area(fill_width, layer=METAL3)
            # connect bitline to sense amp
            data_pin_y = self.sense_amp_array_inst.get_pin("data[0]").by()
            y_base = data_pin_y - self.get_line_end_space(METAL2) - self.m2_width
            pin_names = ["bl", "br"]
            for i in range(2):
                pin_name = pin_names[i]
                y_offset = y_base - (1 - i) * self.m2_pitch
                sense_pin = self.sense_amp_array_inst.get_pin(pin_name + "[{}]".format(col))
                driver_pin = self.write_driver_array_inst.get_pin(pin_name + "[{}]".format(col))
                x_offset = driver_pin.cx() - 0.5 * self.m2_width
                self.add_rect(METAL2, offset=vector(x_offset, driver_pin.uy()),
                              height=y_offset - driver_pin.uy() + self.m2_width)
                self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                              width=sense_pin.cx() - x_offset)
                x_offset = sense_pin.cx() - 0.5 * self.m2_width
                self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                              height=sense_pin.by() - y_offset + self.m2_width)

                self.add_rect(METAL3, offset=vector(sense_pin.cx() - 0.5 * fill_width,
                                                    sense_pin.by()),
                              width=fill_width, height=fill_height)
                via_offset = vector(x_offset, sense_pin.by())
                self.add_contact(m2m3.layer_stack, offset=via_offset)
                self.add_contact(m3m4.layer_stack, offset=via_offset)
            # route data_bar
            flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(col))
            y_offset = flop_pin.uy() + self.get_line_end_space(METAL2)
            self.add_rect(METAL2, offset=flop_pin.ul(),
                          height=y_offset + self.m2_width - flop_pin.uy())
            self.add_rect(METAL2, offset=vector(flop_pin.lx(), y_offset),
                          width=driver_pin.lx() - flop_pin.lx())
            self.add_rect(METAL2, offset=vector(driver_pin.lx(), y_offset),
                          height=driver_pin.by() - y_offset)

            # route data
            flop_pin = self.data_in_flops_inst.get_pin("dout[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data[{}]".format(col))
            self.add_contact(m2m3.layer_stack, offset=flop_pin.ul() - vector(0, m2m3.height))
            y_offset = flop_pin.uy() - 0.5 * m2m3.height - 0.5 * self.m3_width
            self.add_rect(METAL3, offset=vector(flop_pin.lx(), y_offset),
                          width=max(self.m3_width, driver_pin.lx() - flop_pin.lx(), key=abs))
            self.add_rect(METAL3, offset=vector(driver_pin.lx(), y_offset),
                          height=driver_pin.by() - y_offset)
            self.add_contact(m2m3.layer_stack,
                             offset=vector(driver_pin.rx(), driver_pin.by()),
                             rotate=90)

            # route mask to be below data-flop input
            data_in = self.data_in_flops_inst.get_pin("din[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("mask[{}]".format(col))
            flop_pin = self.mask_in_flops_inst.get_pin("dout[{}]".format(col))

            # m2 from mask to align with data flop
            y_offset = flop_pin.uy() + self.get_line_end_space(METAL2)
            self.add_rect(METAL2, offset=flop_pin.ul(), width=flop_pin.width(),
                          height=y_offset + self.m2_width - flop_pin.uy())
            x_offset = driver_pin.lx()
            if col % 2 == 0:
                self.add_rect(METAL2, offset=vector(flop_pin.lx(), y_offset),
                              width=x_offset - flop_pin.lx())
            else:
                self.add_rect(METAL2, offset=vector(flop_pin.rx(), y_offset),
                              width=x_offset - flop_pin.rx())

            self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                          height=data_in.by() - y_offset)
            y_offset = data_in.by()
            # via from m2 to m4
            via_offset = vector(x_offset, y_offset)
            self.add_contact(m2m3.layer_stack, offset=via_offset)
            self.add_contact(m3m4.layer_stack, offset=via_offset)
            fill_height = m3m4.height
            fill_height, fill_width = self.calculate_min_m1_area(fill_height, layer=METAL3)
            # fill and m4 to driver input
            self.add_rect(METAL3,
                          offset=vector(via_offset.x + 0.5 * (m3m4.contact_width - fill_width),
                                        via_offset.y), width=fill_width, height=fill_height)
            self.add_rect(METAL4, offset=via_offset, height=driver_pin.by() - via_offset.y)

            # driver mask input m4 to m2
            if col % 2 == 0:
                via_x = driver_pin.lx() + m2m3.height
                fill_x = via_x - fill_width
            else:
                via_x = driver_pin.rx()
                fill_x = via_x - m2m3.height
            self.add_contact(m2m3.layer_stack,
                             offset=vector(via_x, driver_pin.by() - 0.5 * m2m3.width),
                             rotate=90)
            via_y = driver_pin.by() + m2m3.width - m3m4.height
            self.add_contact(m3m4.layer_stack, offset=vector(driver_pin.lx(), via_y))
            self.add_rect(METAL3, offset=vector(fill_x, via_y), width=fill_width,
                          height=fill_height)

            # route power, gnd
            self.route_all_power(self.write_driver_array_inst)

    def route_flops(self):
        fill_height = m3m4.height
        fill_height, fill_width = self.calculate_min_m1_area(fill_height, layer=METAL3)

        self.route_all_power(self.mask_in_flops_inst)
        self.route_all_power(self.data_in_flops_inst)

        for word in range(self.word_size):
            # align data input to be below mask flop output
            data_in = self.data_in_flops_inst.get_pin("din[{}]".format(word))
            driver_pin = self.write_driver_array_inst.get_pin("mask[{}]".format(word))
            y_offset = data_in.by() - self.get_wide_space(METAL4) - fill_height
            x_offset = data_in.lx()
            offset = vector(x_offset, y_offset)
            self.add_rect(METAL2, offset=offset, height=data_in.by() - y_offset)
            self.add_contact(m2m3.layer_stack, offset=offset)
            x_offset = data_in.lx() if word % 2 == 0 else data_in.rx()
            self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                          width=driver_pin.cx() - x_offset, height=fill_height)
            self.add_contact(m3m4.layer_stack, offset=vector(driver_pin.lx(), y_offset))

            self.add_layout_pin("DATA[{}]".format(word), METAL4,
                                offset=vector(driver_pin.lx(), self.min_point),
                                height=y_offset - self.min_point)
            # mask in
            mask_in = self.mask_in_flops_inst.get_pin("din[{}]".format(word))
            y_offset = mask_in.by() - self.get_wide_space(METAL4) - fill_height - 0.5 * m3m4.height
            via_offset = vector(mask_in.lx(), y_offset)
            self.add_rect(METAL2, offset=via_offset, height=mask_in.by() - via_offset.y)
            self.add_rect(METAL3, offset=vector(mask_in.cx() - 0.5 * fill_width, y_offset),
                          width=fill_width, height=fill_height)
            self.add_contact(m2m3.layer_stack, offset=via_offset)
            self.add_contact(m3m4.layer_stack, offset=via_offset)
            self.add_layout_pin("MASK[{}]".format(word), METAL4,
                                offset=vector(via_offset.x, self.min_point),
                                height=via_offset.y - self.min_point)

    def route_tri_gate(self):
        self.route_all_power(self.tri_gate_array_inst)
        fill_height = m3m4.height
        fill_height, fill_width = self.calculate_min_m1_area(fill_height, layer=METAL3)

        write_driver_m3 = self.write_driver_array.child_mod.get_layer_shapes(METAL3, recursive=True)
        top_m3 = max(write_driver_m3, key=lambda x: x.uy()).uy()
        sense_out_y = self.write_driver_array_inst.by() + top_m3 + self.get_wide_space(METAL3)

        for word in range(self.word_size):
            mask_in = self.mask_in_flops_inst.get_pin("din[{}]".format(word))
            tri_in = self.tri_gate_array_inst.get_pin("in[{}]".format(word))
            # tri input to sense_out_y
            y_offset = mask_in.by() - 0.5 * m3m4.height
            self.add_contact(m3m4.layer_stack, offset=vector(mask_in.lx(), y_offset))
            self.add_contact(m2m3.layer_stack, offset=vector(tri_in.lx(), y_offset))
            self.add_rect(METAL3, offset=vector(mask_in.lx(), y_offset),
                          height=m3m4.height, width=tri_in.lx() - mask_in.lx())
            self.add_rect(METAL2, offset=tri_in.ul(), height=y_offset - tri_in.uy())

            self.add_rect(METAL4, offset=vector(mask_in.lx(), y_offset),
                          height=sense_out_y - y_offset)
            # sense_out_y to sense amp out
            sense_out = self.sense_amp_array_inst.get_pin("data[{}]".format(word))
            self.add_contact(m3m4.layer_stack, offset=vector(mask_in.lx(), sense_out_y))
            if word % 2 == 0:
                self.add_rect(METAL3, offset=vector(mask_in.lx(), sense_out_y),
                              width=sense_out.rx() - mask_in.lx(), height=m3m4.height)
            else:
                self.add_rect(METAL3, offset=vector(mask_in.lx(), sense_out_y),
                              width=sense_out.lx() - mask_in.lx(), height=m3m4.height)
            y_offset = sense_out_y + m3m4.height
            self.add_contact(m2m3.layer_stack, offset=vector(sense_out.lx(), sense_out.by()))
            self.add_rect(METAL3, offset=vector(sense_out.lx(), y_offset), width=sense_out.width(),
                          height=sense_out.by() - y_offset)

            # tri output to data pin
            tri_out = self.tri_gate_array_inst.get_pin("out[{}]".format(word))
            data_pin = self.get_pin("DATA[{}]".format(word))
            self.add_rect(METAL2, offset=vector(data_pin.lx(), tri_out.by()),
                          width=tri_out.cx() - data_pin.lx(), height=m2m3.height)
            offset = vector(data_pin.cx(), tri_out.by() + 0.5 * m2m3.height)
            self.add_contact_center(m2m3.layer_stack, offset=offset)
            self.add_contact_center(m3m4.layer_stack, offset=offset)
            self.add_rect_center(METAL3, offset=offset, width=fill_width, height=fill_height)

    def route_wordline_driver(self):
        for row in range(self.num_rows):
            self.copy_layout_pin(self.wordline_driver_inst, "decode[{}]".format(row),
                                 "dec_out[{}]".format(row))
        fill_width = self.mid_vdd.width()
        fill_width, fill_height = self.calculate_min_m1_area(fill_width, min_height=self.m2_width,
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

    def calculate_rail_vias(self):
        pass

    def add_decoder_power_vias(self):
        pass

    def get_all_power_pins(self):
        """All power pins except bitcell"""
        instances = [self.wordline_driver_inst, self.precharge_array_inst, self.sense_amp_array_inst,
                     self.write_driver_array_inst, self.data_in_flops_inst, self.mask_in_flops_inst,
                     self.tri_gate_array_inst]

        def get_power_pins(inst):
            results = inst.get_pins("vdd") if "vdd" in inst.mod.pins else []
            results += inst.get_pins("gnd") if "gnd" in inst.mod.pins else []
            return results

        all_power_pins = []
        for inst_ in instances:
            all_power_pins.extend(get_power_pins(inst_))
        return all_power_pins

    def add_right_rails_vias(self):
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

    def route_body_tap_supplies(self):
        pass

    def route_control_buffers_power(self):
        pass

    def route_intra_array_power_grid(self):
        """Route M4 power in between bitcell array"""
        debug.info(1, "Route intra-array power grid")
        bitcell_power = (self.bitcell_array_inst.get_pins("vdd")
                         + self.bitcell_array_inst.get_pins("gnd"))
        bitcell_power = [x for x in bitcell_power if x.layer == METAL3]

        # middle and right vdd
        for pin in [self.mid_vdd, self.right_vdd]:
            for power_pin in bitcell_power:
                if power_pin.name == "vdd":
                    self.add_contact_center(m3m4.layer_stack, size=[1, 2],
                                            offset=vector(pin.cx(), power_pin.cy()),
                                            rotate=90)

        bitcell_width = self.bitcell.width
        cell_spacing = OPTS.bitcell_vdd_spacing
        # wide enough to accommodate two vias
        bitcell_rail_top = self.mid_gnd.uy()

        rail_width = m3m4.height
        wide_space = self.get_wide_space(METAL4)
        parallel_space = self.get_parallel_space(METAL4)

        write_driver_power = (self.write_driver_array_inst.get_pins("vdd")
                              + self.write_driver_array_inst.get_pins("gnd"))
        write_driver_power_y = [x.uy() for x in write_driver_power if x.layer == METAL3]
        pin_top = max(write_driver_power_y)

        intermediate_top = self.precharge_array_inst.uy() + self.rail_height + wide_space
        bitcell_rail_y = intermediate_top - self.rail_height

        pin_names = ["vdd", "gnd"]

        all_power_pins = [x for x in self.get_all_power_pins() if x.layer == METAL3]

        control_buffers_power = (self.control_buffers_inst.get_pins("vdd")
                                 + self.control_buffers_inst.get_pins("gnd"))
        fill_width = m3m4.height
        _, m2_fill_height = self.calculate_min_m1_area(fill_width, layer=METAL2)
        _, m3_fill_height = self.calculate_min_m1_area(fill_width, layer=METAL3)

        rail_pitch = wide_space + rail_width
        for cell_index in range(cell_spacing, self.num_cols, cell_spacing):
            mid_x = cell_index * bitcell_width
            # power pin from min point to write driver array
            x_offset = mid_x - 0.5 * wide_space - rail_width
            for pin_name in pin_names:
                pin = self.add_layout_pin(pin_name, METAL4,
                                          offset=vector(x_offset, self.min_point),
                                          width=rail_width, height=pin_top - self.min_point)
                for power_pin in all_power_pins:
                    if power_pin.cy() < pin.uy() and power_pin.name == pin_name:
                        self.add_contact_center(m3m4.layer_stack,
                                                offset=vector(pin.cx(), power_pin.cy()),
                                                rotate=90)
                if x_offset > self.control_buffers_inst.rx() + pin.width():
                    for power_pin in control_buffers_power:
                        if power_pin.name == pin_name:
                            via_offset = vector(pin.cx(), power_pin.cy())
                            self.add_contact_center(m1m2.layer_stack, via_offset)
                            self.add_contact_center(m2m3.layer_stack, via_offset)
                            self.add_contact_center(m3m4.layer_stack, via_offset)
                            self.add_rect_center(METAL2, offset=via_offset, width=fill_width,
                                                 height=m2_fill_height)
                            self.add_rect_center(METAL3, offset=via_offset, width=fill_width,
                                                 height=m3_fill_height)

                x_offset += rail_pitch
            # write driver array to bitcell
            x_offset = mid_x - 0.5 * parallel_space - self.m4_width
            for i in range(2):
                pin_name = pin_names[i]
                rect = self.add_rect(METAL4, offset=vector(x_offset, pin_top - self.m4_width),
                                     width=self.m4_width,
                                     height=intermediate_top - pin_top + self.m4_width)
                for power_pin in all_power_pins:
                    if (rect.by() < power_pin.cy() < rect.uy() and power_pin.name == pin_name
                            and power_pin.height() >= m3m4.height):
                        self.add_contact_center(m3m4.layer_stack,
                                                offset=vector(rect.cx(), power_pin.cy()))
                x_offset += parallel_space + self.m4_width

            # through bitcell array
            x_offset = mid_x - 0.5 * wide_space - rail_width
            for i in range(2):
                pin_name = pin_names[i]
                pin = self.add_layout_pin(pin_name, METAL4,
                                          offset=vector(x_offset, bitcell_rail_y),
                                          width=rail_width,
                                          height=bitcell_rail_top - bitcell_rail_y)
                for power_pin in bitcell_power:
                    if power_pin.name == pin_name:
                        self.add_contact_center(m3m4.layer_stack,
                                                offset=vector(pin.cx(), power_pin.cy()),
                                                rotate=90)

                x_offset += wide_space + rail_width
