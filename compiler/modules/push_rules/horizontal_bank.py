from typing import List

from base.design import METAL2
from base.geometry import instance
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from base.well_implant_fills import well_implant_instance_fills
from globals import OPTS
from modules.push_rules.latched_control_logic import LatchedControlLogic
from modules.shared_decoder.cmos_bank import CmosBank


class HorizontalBank(CmosBank):
    rotation_for_drc = GDS_ROT_270

    @staticmethod
    def get_module_list():
        return ["bitcell", "decoder", "ms_flop_array", "wordline_buffer",
                "bitcell_array", "sense_amp_array", "precharge_array",
                "write_driver_array", "tri_gate_array", "flop_buffer"]

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
            args.remove("write_en_bar")
        super().connect_inst(args, check)

    def create_control_buffers(self):
        self.control_buffers = LatchedControlLogic()
        self.add_mod(self.control_buffers)

    def create_control_flop(self):
        self.control_flop = self.create_module("flop_buffer", OPTS.control_flop,
                                               OPTS.control_flop_buffers, dummy_indices=[0])

    def connect_control_buffers(self):
        self.connect_inst(["bank_sel_buf", "read_buf", "clk", "sense_trig", "precharge_trig",
                           "clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                           "write_en", "sense_en", "tri_en", "sample_en_bar", "vdd", "gnd"])

    def get_control_rails_destinations(self):
        destination_pins = {
            "sense_en": self.sense_amp_array_inst.get_pins("en"),
            "tri_en": self.tri_gate_array_inst.get_pins("en"),
            "sample_bar": self.sense_amp_array_inst.get_pins("sampleb"),
            "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
            "clk_buf": self.mask_in_flops_inst.get_pins("clk"),
            "clk_bar": self.data_in_flops_inst.get_pins("clk"),
            "write_en": self.write_driver_array_inst.get_pins("en"),
        }
        if True:  # differentiate left right
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
        self.trigate_y = (control_logic_top + (len(top_pins) * self.bus_pitch)) + self.get_line_end_space(METAL2)
        self.control_rail_offsets = {}

        for i in range(len(top_pins)):
            self.control_rail_offsets[top_pins[i]] = control_logic_top + i * self.bus_pitch

        y_offset = 0
        for i in reversed(range(len(bottom_pins))):
            self.control_rail_offsets[bottom_pins[i]] = y_offset
            y_offset += self.bus_pitch

    def add_control_rails(self):
        destination_pins = self.get_control_rails_destinations()
        num_rails = len(destination_pins.keys())
        x_offset = (self.mid_vdd_offset - (num_rails * self.control_rail_pitch)
                    - (self.wide_m1_space - self.line_end_space))
        rail_names = list(sorted(destination_pins.keys(),
                                 key=lambda x: self.control_buffers_inst.get_pin(x).lx()))
        for rail_name in rail_names:
            self.add_control_rail(rail_name, destination_pins[rail_name],
                                  x_offset, self.control_rail_offsets[rail_name])
            x_offset += self.control_rail_pitch

        self.leftmost_rail = getattr(self, rail_names[0] + "_rail")

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

    def get_precharge_y(self):
        return self.get_module_y_space(self.sense_amp_array_inst, self.precharge_array)

    def add_wordline_driver(self):
        x_offset = self.mid_vdd_offset - (self.wordline_buffer.width + self.wide_m1_space)
        self.wordline_driver_inst = self.add_inst(name="wordline_buffer", mod=self.wordline_buffer,
                                                  offset=vector(x_offset, self.bitcell_array_inst.by()))
        args = ["dec_out[{}]".format(x) for x in range(self.num_rows)]
        args += ["wl[{}]".format(x) for x in range(self.num_rows)]
        self.connect_inst(args + ["vdd", "gnd"])

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
        def fill_dual_mirror(bottom_inst, top_inst):
            """Fill between modules that are mirrored in groups of two"""
            y_space_ = top_inst.by() - bottom_inst.uy()
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
        y_space = self.write_driver_array_inst.by() - self.data_in_flops_inst.uy()
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 0, 0)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 0, 1)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 1, 2)
        fill_single_mirror(self.data_in_flops_inst, self.write_driver_array_inst, 1, 3)

        # write_driver -> sense amp
        y_space = self.sense_amp_array_inst.by() - self.write_driver_array_inst.uy()
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 0, 0, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 1, 0, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 2, 1, 2)
        fill_single_mirror(self.write_driver_array_inst, self.sense_amp_array_inst, 3, 1, 2)

        # sense amp -> precharge
        y_space = self.precharge_array_inst.by() - self.sense_amp_array_inst.uy()
        if self.col_mux_array_inst is None:
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 0, 0)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 0, 1)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 1, 2)
            fill_single_mirror(self.sense_amp_array_inst, self.precharge_array_inst, 1, 3)
