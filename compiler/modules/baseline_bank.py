import itertools
import math
from abc import ABC
from copy import copy
from importlib import reload
from math import log

import debug
import tech
from base import utils
from base.contact import m2m3, m1m2, m3m4, contact, cross_m2m3, cross_m1m2
from base.design import design, METAL2, METAL3, METAL1, METAL4, DRAWING, NWELL, PWELL
from base.geometry import NO_MIRROR
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills, evaluate_vertical_metal_spacing, \
    join_vertical_adjacent_module_wells, evaluate_vertical_module_spacing
from globals import OPTS
from modules.control_buffers_repeaters_mixin import ControlBuffersRepeatersMixin
from tech import delay_strategy_class

LEFT_FILL = "left"
MID_FILL = "mid"
RIGHT_FILL = "right"

JOIN_TOP_ALIGN = "top"
JOIN_BOT_ALIGN = "bottom"

EXACT = "exact"


class BaselineBank(design, ControlBuffersRepeatersMixin, ABC):
    control_buffers = None

    def __init__(self, word_size, num_words, words_per_row, num_banks=1, name="", adjacent_bank=None):
        if name == "":
            name = "bank_{0}_{1}{2}".format(word_size, num_words, "_left" if adjacent_bank else "")

        self.is_left_bank = adjacent_bank is not None
        self.adjacent_bank = adjacent_bank
        design.__init__(self, name)
        debug.info(2, "create {0} of size {1} with {2} words".format(name, word_size, num_words))

        self.set_modules(self.get_module_list())

        self.word_size = word_size
        self.num_words = num_words
        self.words_per_row = words_per_row
        self.num_banks = num_banks

        # The local control signals are gated when we have bank select logic,
        # so this prefix will be added to all of the input signals.
        self.prefix = "gated_"

        self.mirror_sense_amp = OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP

        self.compute_sizes()
        debug.info(1, "Create modules")
        self.create_modules()
        debug.info(1, "Calculate rail offsets")
        self.calculate_rail_offsets()
        debug.info(1, "Add modules")
        self.add_modules()
        debug.info(1, "Route bank layout")
        self.route_layout()
        self.add_pins()
        self.calculate_dimensions()
        self.add_lvs_correspondence_points()
        debug.info(1, "Offset bank coordinates to origin")
        self.offset_all_coordinates()

    def set_modules(self, mod_list):
        """
        Imports modules in mod_list by name. The name is split into module_name, class_name using . separator
        If no '.' in name, class_name is the same as module_name.
        The imported class is set as an instance property with name mod_{mod_name}
        """
        for mod_name in mod_list:
            config_mod_name = getattr(OPTS, mod_name)
            if "." in config_mod_name:
                config_mod_name, class_name = config_mod_name.split(".")
            else:
                class_name = config_mod_name
            class_file = reload(__import__(config_mod_name))
            mod_class = getattr(class_file, class_name)
            setattr(self, "mod_" + mod_name, mod_class)

    @staticmethod
    def get_module_list():
        """Returns a list of modules that will be imported as specified in OPTS"""
        return ["tri_gate", "bitcell", "decoder", "ms_flop_array", "ms_flop_array_horizontal", "wordline_driver",
                "bitcell_array", "sense_amp_array", "precharge_array", "flop_buffer",
                "column_mux_array", "write_driver_array", "tri_gate_array"]

    def add_pins(self):
        """Add bank pins"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            if self.has_mask_in:
                self.add_pin("MASK[{0}]".format(i))
        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                self.add_pin("sel[{}]".format(i))
        for i in range(self.num_rows):
            self.add_pin("dec_out[{}]".format(i))

        self.add_pin_list(self.control_buffers.get_input_pin_names() +
                          ["clk_buf", "clk_bar", "vdd", "gnd"])

    def calculate_dimensions(self):
        """Calculate bank width and height"""
        self.width = self.bitcell_array_inst.rx() - self.wordline_driver_inst.lx()
        self.height = self.bitcell_array_inst.uy() - self.control_buffers_inst.by()

    def add_modules(self):
        """Add bitcell array and peripherals"""
        self.add_control_buffers()
        self.add_tri_gate_array()
        self.add_data_mask_flops()
        self.add_write_driver_array()
        self.add_sense_amp_array()
        self.add_column_mux_array()
        self.add_precharge_array()
        self.add_bitcell_array()
        self.fill_vertical_module_spaces()
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
        self.min_point = min(self.min_point, min(map(lambda x: x.by(), self.insts)))

        self.add_vdd_gnd_rails()

    def route_layout(self):
        self.route_control_buffers()
        self.route_control_flops()
        self.route_precharge()
        self.route_column_mux()
        self.route_sense_amp()
        self.route_bitcell()
        self.route_write_driver()
        self.route_flops()
        self.route_tri_gate()
        self.route_wordline_driver()

        # to keep track of offsets used for repeaters or inter-array power
        self.occupied_m4_bitcell_indices = []

        if hasattr(OPTS, "buffer_repeaters_x_offset"):
            self.create_control_buffer_repeaters()
            self.route_control_buffer_repeaters()

        self.add_m2m4_power_rails_vias()
        self.route_body_tap_supplies()

        self.route_intra_array_power_grid()

    def get_module_exceptions(self):
        return []

    def create_left_bank_modules(self):
        """Copies modules from the specified adjacent bank"""
        for module_name in self.get_module_list() + ["control_flop", "msf_mask_in",
                                                     "msf_data_in"]:
            if not hasattr(self.adjacent_bank, module_name):
                continue
            adjacent_mod = getattr(self.adjacent_bank, module_name)
            setattr(self, module_name, adjacent_mod)
            self.add_mod(adjacent_mod)
        self.create_control_buffers()

    def create_modules(self):
        """Create modules that will be added to bank"""
        if self.is_left_bank:
            return self.create_left_bank_modules()

        self.msf_mask_in = self.create_module('ms_flop_array', columns=self.num_cols,
                                              word_size=self.word_size, flop_mod=OPTS.mask_in_flop,
                                              flop_tap_name=OPTS.mask_in_flop_tap, align_bitcell=True)

        if not getattr(OPTS, "data_in_flop", OPTS.mask_in_flop) == OPTS.mask_in_flop:
            self.msf_data_in = self.create_module('ms_flop_array', columns=self.num_cols,
                                                  word_size=self.word_size,
                                                  align_bitcell=True, flop_mod=OPTS.data_in_flop,
                                                  flop_tap_name=OPTS.data_in_flop_tap)
        else:
            self.msf_data_in = self.msf_mask_in

        self.write_driver_array = self.create_module('write_driver_array', columns=self.num_cols,
                                                     word_size=self.word_size)

        self.bitcell_array = self.create_module('bitcell_array', cols=self.num_cols, rows=self.num_rows)
        self.bitcell = self.bitcell_array.cell

        self.tri_gate_array = self.create_module('tri_gate_array', columns=self.num_cols, word_size=self.word_size)

        self.sense_amp_array = self.create_module('sense_amp_array', word_size=self.word_size,
                                                  words_per_row=self.words_per_row)

        if self.col_addr_size > 0:
            self.column_mux_array = self.create_module('column_mux_array', word_size=self.word_size,
                                                       columns=self.num_cols)

        # run optimizations
        delay_strategy = delay_strategy_class()(self)
        self.wordline_driver = delay_strategy.run_optimizations()

        self.precharge_array = self.create_module('precharge_array', columns=self.num_cols, size=OPTS.precharge_size)

        self.create_control_buffers()

        self.decoder = self.create_module('decoder', rows=self.num_rows)

        self.create_control_flop()

    def create_module(self, mod_name, *args, **kwargs):
        """Creates mod from class 'mod_{mod_name}. args, kwargs are passed to class"""
        if mod_name not in self.get_module_list():
            return
        debug.info(2, "Creating module {} with args {} {}".format(mod_name,
                                                                  " ".join(map(str, args)),
                                                                  kwargs))
        mod = getattr(self, 'mod_' + mod_name)(*args, **kwargs)
        self.add_mod(mod)
        return mod

    def compute_sizes(self):
        """  Computes the required sizes to create the bank """

        self.num_rows = int(self.num_words / self.words_per_row)
        self.num_cols = int(self.words_per_row * self.word_size)

        self.row_addr_size = int(log(self.num_rows, 2))
        self.col_addr_size = int(log(self.words_per_row, 2))
        self.addr_size = self.col_addr_size + self.row_addr_size

        debug.check(self.addr_size == self.col_addr_size + self.row_addr_size, "Invalid address break down.")
        debug.check(self.num_rows * self.num_cols == self.word_size * self.num_words, "Invalid bank sizes.")

        # Width for left gnd rail
        dummy_via = contact(layer_stack=m3m4.layer_stack, dimensions=[1, 2])
        self.vdd_rail_width = dummy_via.height
        self.gnd_rail_width = self.vdd_rail_width

        # m2 fill width for m1-m3 via
        self.via_m2_fill_height = m1m2.second_layer_height
        _, self.via_m2_fill_width = self.calculate_min_area_fill(width=self.via_m2_fill_height, layer=METAL2)

        # The central bus is the column address (both polarities), row address
        self.num_addr_lines = self.row_addr_size

        # M1/M2 routing pitch is based on contacted pitch
        self.m1_pitch = m1m2.width + self.get_parallel_space(METAL1)
        self.m2_pitch = m2m3.width + self.get_parallel_space(METAL2)
        self.m3_pitch = m2m3.width + self.get_parallel_space(METAL3)

    def get_wordline_in_net(self):
        return "dec_out[{}]"

    def create_control_buffers(self):
        """Create control logic buffers"""
        pass

    def create_control_flop(self):
        self.control_flop = self.create_module("flop_buffer", OPTS.control_flop,
                                               OPTS.control_flop_buffers)

    def get_control_names(self):
        """Get outputs of control logic buffers"""
        return self.control_buffers.get_output_pin_names()

    def calculate_rail_offsets(self):
        """Calculate control rails y_offsets, triate_y, control_logic_y, mid_vdd, mid_gnd"""
        self.control_rail_pitch = self.bus_pitch

        self.control_names = self.get_control_names()
        control_outputs = [x for x in self.control_names if x in self.control_buffers.pins]

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
        module_space = 0.5 * control_vdd.height() + self.get_parallel_space(METAL3)

        if len(bottom_pins) > 0:
            self.logic_buffers_bottom = ((len(bottom_pins) * self.bus_pitch)
                                         - self.bus_space + module_space)
        else:
            self.logic_buffers_bottom = 0

        control_logic_top = self.get_control_logic_top(module_space)

        self.trigate_y = (control_logic_top + (len(top_pins) * self.bus_pitch)) + self.get_line_end_space(METAL2)
        self.control_rail_offsets = {}

        for i in range(len(top_pins)):
            self.control_rail_offsets[top_pins[i]] = control_logic_top + i * self.bus_pitch

        y_offset = 0
        for i in reversed(range(len(bottom_pins))):
            self.control_rail_offsets[bottom_pins[i]] = y_offset
            y_offset += self.bus_pitch

        self.top_control_rails, self.bottom_control_rails = top_pins, bottom_pins
        # mid power rails
        self.wide_power_space = self.get_wide_space(METAL2)
        self.mid_gnd_offset = self.get_mid_gnd_offset()
        self.mid_vdd_offset = self.mid_gnd_offset - self.wide_power_space - self.vdd_rail_width

        fill_height = m2m3.second_layer_height + self.m2_width
        (self.fill_height, self.fill_width) = self.calculate_min_area_fill(fill_height, self.m2_width)

    def get_control_logic_top(self, module_space):
        return self.logic_buffers_bottom + self.control_buffers.height + module_space

    def connect_control_buffers(self):
        connections = self.connections_from_mod(self.control_buffers, [
            ("bank_sel", "bank_sel_buf"),
            ("read", "read_buf")
        ])
        self.connect_inst(connections)

    def add_control_buffers(self):
        """Add control logic buffers"""
        offset = vector(0, self.logic_buffers_bottom)
        self.control_buffers_inst = self.add_inst("control_buffers", mod=self.control_buffers,
                                                  offset=offset)
        self.connect_control_buffers()

    def add_control_flops(self):
        x_offset, y_offset = self.get_control_flops_offset()

        self.bank_sel_buf_inst = self.add_inst("bank_sel_buf", mod=self.control_flop,
                                               offset=vector(x_offset, y_offset))
        self.connect_inst(["bank_sel", "clk", "bank_sel_buf", "vdd", "gnd"])

        offset = self.bank_sel_buf_inst.ul() + vector(0, self.control_flop.height)
        self.read_buf_inst = self.add_inst("read_buf", mod=self.control_flop, offset=offset, mirror="MX")
        self.connect_inst(["read", "clk", "read_buf", "vdd", "gnd"])

        y_offset = (self.bank_sel_buf_inst.by() - self.get_wide_space(METAL2)
                    - self.bus_pitch)
        self.cross_clk_rail_y = min(y_offset, self.control_buffers_inst.by() - self.bus_pitch)
        self.min_point = min(self.min_point, self.cross_clk_rail_y)

    def get_non_flop_control_inputs(self):
        """Get control buffers inputs that don't go through flops"""
        precharge_trigger = ["precharge_trig"] * self.control_buffers.use_precharge_trigger
        return ["sense_trig"] + precharge_trigger

    def get_row_decoder_control_flop_space(self):
        flop_vdd = self.control_flop.get_pins("vdd")[0]
        return flop_vdd.height() + self.get_wide_space(flop_vdd.layer)

    def get_control_flops_offset(self):
        wide_space = self.get_wide_space(METAL2)
        # place below predecoder
        flop_vdd = self.control_flop.get_pins("vdd")[0]
        row_decoder_flop_space = self.get_row_decoder_control_flop_space()
        space = utils.ceil(1.2 * self.bus_space)
        row_decoder_col_decoder_space = flop_vdd.height() + 2 * space + self.bus_width

        # y offset based on control buffer
        y_offset_control_buffer = max(self.control_buffers_inst.by() + row_decoder_flop_space,
                                      self.control_buffers_inst.cy() - self.control_flop.height)

        row_decoder_y = self.bitcell_array_inst.uy() - self.decoder.height - self.bitcell.height
        y_offset = min(y_offset_control_buffer,
                       row_decoder_y - row_decoder_flop_space - 2 * self.control_flop.height)

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

        # place to the left of bottom rail

        # ensure no clash with rails above control_buffer
        top_rails = [getattr(self, x + "_rail") for x in self.top_control_rails]
        bottom_rails = [getattr(self, x + "_rail") for x in self.bottom_control_rails]
        control_top = y_offset + 2 * self.control_flop.height + row_decoder_flop_space
        rails_below_control_flops = [x for x in top_rails + top_rails if x.by() < control_top]
        if rails_below_control_flops:
            leftmost_top_rail_x = min(rails_below_control_flops, key=lambda x: x.lx()).lx()
        else:
            if self.bottom_control_rails:
                leftmost_top_rail_x = min(bottom_rails, key=lambda x: x.lx()).lx()
            else:
                leftmost_top_rail_x = self.mid_vdd_offset

        num_control_inputs = len(self.get_non_flop_control_inputs())
        num_flop_inputs = 2
        num_inputs = num_control_inputs + num_flop_inputs + 1

        bank_sel_out_rail_x = (leftmost_top_rail_x - wide_space - num_inputs * self.bus_pitch
                               + self.bus_space)
        x_offset = (bank_sel_out_rail_x - wide_space - self.control_flop.width)

        self.control_flop_y = y_offset
        return x_offset, y_offset

    def add_tri_gate_array(self):
        """ data tri gate to drive the data bus """

        y_offset = self.trigate_y

        self.tri_gate_array_inst = self.add_inst(name="tri_gate_array", mod=self.tri_gate_array,
                                                 offset=vector(0, y_offset))

        replacements = [("out[", "DATA["),
                        ("in_bar[", "sense_out_bar["), ("in[", "sense_out["),
                        ("en", "tri_en", EXACT), ("en_bar", "tri_en_bar", EXACT)]
        connections = self.connections_from_mod(self.tri_gate_array, replacements)
        self.connect_inst(connections)

    @staticmethod
    def connections_from_mod(mod: design, replacements=None):
        connections = copy(mod.pins)
        if not replacements:
            return connections
        for pairs in replacements:
            if len(pairs) == 2:
                source, replacement = pairs
                connections = [x.replace(source, replacement) for x in connections]
            elif len(pairs) == 3 and pairs[2] == EXACT:
                source, replacement, _ = pairs
                connections = [replacement if x == source else x for x in connections]
        return connections

    def calculate_bitcell_aligned_spacing(self, top_module, bottom_module,
                                          num_rails=0, min_space=None):

        m2_m3_space = evaluate_vertical_metal_spacing(top_module.child_mod,
                                                      bottom_module.child_mod,
                                                      num_rails)
        min_space = max(m2_m3_space, min_space or -bottom_module.height)

        top_modules = [top_module.child_mod]
        bottom_modules = [bottom_module.child_mod]
        if (getattr(top_module, "body_tap", None) and
                getattr(bottom_module, "body_tap", None)):
            top_modules.append(top_module.body_tap)
            bottom_modules.append(bottom_module.body_tap)
        return evaluate_vertical_module_spacing(top_modules=top_modules,
                                                bottom_modules=bottom_modules,
                                                min_space=min_space)

    def get_mask_flops_y_offset(self, flop=None, flop_tap=None):
        y_space = self.calculate_bitcell_aligned_spacing(self.msf_mask_in,
                                                         self.tri_gate_array, num_rails=2)
        y_offset = self.tri_gate_array_inst.uy() + y_space
        return y_offset

    def get_data_flops_y_offset(self):
        bottom_mod = self.msf_mask_in if self.has_mask_in else self.tri_gate_array
        y_space = self.calculate_bitcell_aligned_spacing(self.msf_data_in, bottom_mod,
                                                         num_rails=2)
        if self.has_mask_in:
            y_base = self.mask_in_flops_inst.uy()
        else:
            y_base = self.tri_gate_array_inst.uy()
        return y_base + y_space

    def add_mask_flops(self):
        write_driver_mod = self.write_driver_array.child_mod
        self.has_mask_in = "mask" in write_driver_mod.pins or "mask_bar" in write_driver_mod.pins
        if not self.has_mask_in:
            self.mask_in_flops_inst = None
            return
        replacements = [("din", "MASK"), ("dout_bar", "mask_in_bar"), ("dout", "mask_in"),
                        ("clk", "clk_buf")]
        connections = self.connections_from_mod(self.msf_mask_in, replacements)
        y_offset = self.get_mask_flops_y_offset()

        self.mask_in_flops_inst = self.add_inst("mask_in", mod=self.msf_mask_in,
                                                offset=vector(0, y_offset))
        self.connect_inst(connections)

    def add_data_flops(self):
        replacements = [("din", "DATA"), ("dout_bar", "data_in_bar"), ("dout", "data_in"),
                        ("clk", "clk_bar")]
        connections = self.connections_from_mod(self.msf_data_in, replacements)
        y_offset = self.get_data_flops_y_offset()
        self.data_in_flops_inst = self.add_inst("data_in", mod=self.msf_data_in,
                                                offset=vector(0, y_offset))
        self.connect_inst(connections)

    def add_data_mask_flops(self):
        self.add_mask_flops()
        self.add_data_flops()

    def get_mask_clk(self):
        return "clk_buf"

    def get_data_clk(self):
        return "clk_bar"

    def get_write_driver_offset(self):
        y_space = self.calculate_bitcell_aligned_spacing(self.write_driver_array,
                                                         self.msf_data_in, num_rails=1)
        y_offset = self.data_in_flops_inst.uy() + y_space
        return vector(self.data_in_flops_inst.lx(), y_offset)

    def add_write_driver_array(self):
        """Temp write driver, replace with mask support"""

        self.write_driver_array_inst = self.add_inst(name="write_driver_array",
                                                     mod=self.write_driver_array,
                                                     offset=self.get_write_driver_offset())

        replacements = [("data_bar[", "data_in_bar["), ("data[", "data_in["),
                        ("mask_bar[", "mask_in_bar["), ("mask[", "mask_in["),
                        ("en_bar", "write_en_bar", EXACT), ("en", "write_en", EXACT)]

        if self.words_per_row > 1:
            replacements.extend([("bl", "bl_out"), ("br", "br_out")])
        connections = self.connections_from_mod(self.write_driver_array, replacements)

        self.connect_inst(connections)

    def get_sense_amp_array_y(self):
        y_space = self.calculate_bitcell_aligned_spacing(self.sense_amp_array,
                                                         self.write_driver_array, num_rails=1)
        return self.write_driver_array_inst.uy() + y_space

    def add_sense_amp_array(self):

        self.sense_amp_array_offset = vector(self.write_driver_array_inst.lx(),
                                             self.get_sense_amp_array_y())
        self.sense_amp_array_inst = self.add_inst(name="sense_amp_array", mod=self.sense_amp_array,
                                                  offset=self.sense_amp_array_offset)
        replacements = [("dout[", "sense_out["), ("dout_bar[", "sense_out_bar["),
                        ("sampleb", "sample_en_bar"), ("chb", "precharge_en_bar"),
                        ("preb", "precharge_en_bar"), ("en", "sense_en", EXACT),
                        ("en_bar", "sense_en_bar", EXACT)]

        if self.words_per_row > 1:
            replacements.extend([("bl", "bl_out"), ("br", "br_out")])
        connections = self.connections_from_mod(self.sense_amp_array, replacements)
        self.connect_inst(connections)

    def get_column_mux_array_y(self):
        y_space = self.calculate_bitcell_aligned_spacing(self.column_mux_array,
                                                         self.sense_amp_array, num_rails=0)
        return self.sense_amp_array_inst.uy() + y_space

    def add_column_mux_array(self):
        if self.col_addr_size == 0:
            self.col_mux_array_inst = None
            return

        y_offset = self.get_column_mux_array_y()
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

    def get_precharge_y(self):
        if self.col_mux_array_inst is None:
            bottom_inst = self.sense_amp_array_inst
        else:
            bottom_inst = self.col_mux_array_inst
        bottom_mod = bottom_inst.mod
        self.precharge_array.child_mod = self.precharge_array.pc_cell

        if self.col_mux_array_inst is None:
            # we place via below precharge bl pin
            bl_pin = bottom_mod.get_pin("bl[0]")
            # find vias and layers used in going from top to bottom pins
            vias, _, fill_layers = contact.get_layer_vias(bl_pin.layer,
                                                          METAL2,
                                                          cross_via=False)
            layers = list(set(fill_layers + [METAL2, bl_pin.layer]))

            y_space = evaluate_vertical_metal_spacing(self.precharge_array.child_mod,
                                                      bottom_mod.child_mod,
                                                      num_rails=0, layers=layers,
                                                      vias=vias, via_space=False)
        else:
            y_space = -bottom_mod.height
        y_space = self.calculate_bitcell_aligned_spacing(self.precharge_array,
                                                         bottom_mod, num_rails=0,
                                                         min_space=y_space)
        return bottom_inst.uy() + y_space

    def get_precharge_mirror(self):
        return NO_MIRROR

    def add_precharge_array(self):
        """ Adding Precharge """
        y_offset = self.get_precharge_y()
        self.precharge_array_inst = self.add_inst(name="precharge_array",
                                                  mod=self.precharge_array,
                                                  mirror=self.get_precharge_mirror(),
                                                  offset=vector(0, y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        temp.extend(["precharge_en_bar", "vdd"])
        self.connect_inst(temp)

    def add_bitcell_array(self):
        """ Adding Bitcell Array """
        if hasattr(tech, "bitcell_precharge_space"):
            y_space = tech.bitcell_precharge_space(self.bitcell_array, self.precharge_array)
        else:
            self.bitcell_array.child_mod = self.bitcell_array.cell
            y_space = self.calculate_bitcell_aligned_spacing(self.bitcell_array,
                                                             self.precharge_array, num_rails=0)

        y_offset = self.precharge_array_inst.uy() + y_space
        self.bitcell_array_inst = self.add_inst(name="bitcell_array",
                                                mod=self.bitcell_array,
                                                offset=vector(0, y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)

    def get_wordline_driver_connections(self):
        temp = []
        for i in range(self.num_rows):
            temp.append(self.get_wordline_in_net().format(i))
        for i in range(self.num_rows):
            temp.append("wl[{0}]".format(i))
        temp.extend(["wordline_en", "vdd", "gnd"])
        return temp

    def add_wordline_driver(self):
        """ Wordline Driver """
        x_offset = self.mid_vdd_offset - (self.wordline_driver.width + self.wide_m1_space)

        self.wordline_driver_inst = self.add_inst(name="wordline_driver", mod=self.wordline_driver,
                                                  offset=vector(x_offset, self.bitcell_array_inst.by()))
        self.connect_inst(self.get_wordline_driver_connections())

    def get_decoder_clk(self):
        return "clk_buf"

    def get_control_rails_destinations(self):
        """Map control logic buffers output pins to peripheral pins"""
        control_outputs = self.control_buffers.get_output_pin_names()
        destination_pins = {}
        for net in control_outputs:
            if net == "wordline_en":
                destination_pins[net] = self.precharge_array_inst.get_pins("en")
                continue
            destinations = []
            for i in range(len(self.conns)):
                if net in self.conns[i]:
                    pin_index = self.conns[i].index(net)
                    inst = self.insts[i]
                    if inst.name == "control_buffers" or inst.name.startswith("right_buffer"):
                        continue
                    pin_name = inst.mod.pins[pin_index]
                    destinations.extend(inst.get_pins(pin_name))
            if not destinations:
                debug.warning("Control buffer output {} not connected".format(net))
            else:
                destination_pins[net] = destinations
        return destination_pins

    def add_cross_contact_center(self, cont, offset, rotate=False, rail_width=None, fill=True):
        """Add a cross contact whose middle is 'offset'.
        Fills the surrounding metal layer with width 'rail_width' to match extents of the contact"""
        super().add_cross_contact_center(cont, offset, rotate)
        if fill:
            self.add_cross_contact_center_fill(cont, offset, rotate, rail_width)

    def add_control_rail(self, rail_name, dest_pins, x_offset, y_offset):
        """Routes the rail from control logic buffer pin with name 'rail_name' to the destinations 'dest_pins'.
           x_offset is the x_offset of the vertical rail.
           y_offset is the y_offset of the horizontal rail from the control logic buffer pin
         """
        control_pin = self.control_buffers_inst.get_pin(rail_name)
        self.add_rect(METAL2, offset=control_pin.ul(), height=y_offset - control_pin.uy())

        self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                      width=control_pin.rx() - x_offset, height=self.bus_width)

        self.add_cross_contact_center(cross_m2m3, offset=vector(control_pin.cx(),
                                                                y_offset + 0.5 * self.bus_width))

        if not dest_pins:
            rail = self.add_rect(METAL3, offset=vector(x_offset, y_offset), height=m2m3.height,
                                 width=self.bus_width)
        else:
            via_offset = vector(x_offset + 0.5 * self.bus_width, y_offset + 0.5 * self.bus_width)

            self.add_cross_contact_center(cross_m2m3, offset=via_offset)
            top_pin = max(dest_pins, key=lambda x: x.uy())
            rail = self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                                 height=top_pin.cy() - y_offset,
                                 width=self.bus_width)
        setattr(self, rail_name + "_rail", rail)
        if rail_name == "wordline_en":
            return

        for dest_pin in dest_pins:
            rail_height = min(self.bus_width, dest_pin.height())
            rail_y = dest_pin.cy() - 0.5 * rail_height

            if dest_pin.layer in [METAL2, METAL3]:
                via = cross_m2m3
                via_rotate = False
            elif dest_pin.layer == METAL1:
                via = cross_m1m2
                via_rotate = True
            else:
                debug.error("Invalid layer", 1)
                break

            rail_layer = METAL3 if dest_pin.layer == METAL2 else dest_pin.layer
            via_x = x_offset + 0.5 * self.bus_width
            via_y = dest_pin.cy()
            self.add_rect(rail_layer, offset=vector(x_offset, rail_y),
                          width=dest_pin.lx() - x_offset, height=rail_height)
            self.add_cross_contact_center(via, offset=vector(via_x, via_y), rotate=via_rotate)
            if dest_pin.layer == METAL2:
                self.add_contact_center(m2m3.layer_stack,
                                        offset=vector(dest_pin.lx() + 0.5 * m2m3.height, dest_pin.cy()),
                                        rotate=90)
                self.add_rect(METAL3, offset=vector(dest_pin.lx(), rail_y),
                              width=m2m3.height, height=rail_height)

    def add_control_rails(self):
        """Add rails from control logic buffers to appropriate peripherals"""

        def get_top_destination_pin_y(rail_name_):
            if not destination_pins[rail_name_]:
                return self.bitcell_array_inst.by()  # will be rightmost
            else:
                return max(destination_pins[rail_name_], key=lambda x: x.cy()).cy()

        destination_pins = self.get_control_rails_destinations()
        num_rails = len(destination_pins.keys())
        x_offset = (self.mid_vdd_offset - (num_rails * self.control_rail_pitch)
                    - (self.wide_m1_space - self.line_end_space))
        rail_names = list(sorted(destination_pins.keys(),
                                 key=lambda x: (-self.control_buffers_inst.get_pin(x).uy(),
                                                get_top_destination_pin_y(x)),
                                 reverse=False))
        self.rail_names = rail_names
        for rail_name in rail_names:
            self.add_control_rail(rail_name, destination_pins[rail_name],
                                  x_offset, self.control_rail_offsets[rail_name])
            x_offset += self.control_rail_pitch

        self.leftmost_rail = getattr(self, rail_names[0] + "_rail")

    def get_right_vdd_offset(self):
        """x offset for right vdd rail"""
        return max(self.bitcell_array_inst.rx(),
                   self.control_buffers_inst.rx()) + self.wide_power_space

    def get_mid_gnd_offset(self):
        """x offset for middle gnd rail"""
        return - 2 * self.wide_m1_space - self.vdd_rail_width

    def add_vdd_gnd_rails(self):
        """Add mid and right power rails"""
        self.height = self.bitcell_array_inst.uy() - self.min_point

        right_vdd_offset = self.get_right_vdd_offset()
        right_gnd_offset = right_vdd_offset + self.vdd_rail_width + self.wide_power_space

        offsets = [self.mid_gnd_offset, right_gnd_offset, self.mid_vdd_offset, right_vdd_offset]
        pin_names = ["gnd", "gnd", "vdd", "vdd"]
        pin_layers = self.get_vdd_gnd_rail_layers()

        attribute_names = ["mid_gnd", "right_gnd", "mid_vdd", "right_vdd"]
        for i in range(4):
            pin = self.add_layout_pin(pin_names[i], pin_layers[i],
                                      vector(offsets[i], self.min_point),
                                      height=self.bitcell_array_inst.uy() - self.min_point +
                                             m1m2.height, width=self.vdd_rail_width)
            setattr(self, attribute_names[i], pin)
        # for IDE assistance
        self.mid_gnd = getattr(self, "mid_gnd")
        self.right_gnd = getattr(self, "right_gnd")
        self.mid_vdd = getattr(self, "mid_vdd")
        self.right_vdd = getattr(self, "right_vdd")

    def get_vdd_gnd_rail_layers(self):
        """Layers for mid and right power rails"""
        return [METAL2, METAL2, METAL2, METAL2]

    def route_all_instance_power(self, inst, via_rotate=90):
        """Connect all vdd and gnd pins to mid and right rails"""
        vdd_pins = [] if "vdd" not in inst.mod.pins else inst.get_pins("vdd")
        for pin in vdd_pins:
            self.route_vdd_pin(pin, via_rotate=via_rotate)

        gnd_pins = [] if "gnd" not in inst.mod.pins else inst.get_pins("gnd")
        for pin in gnd_pins:
            self.route_gnd_pin(pin, via_rotate=via_rotate)
            self.add_power_via(pin, self.right_gnd, via_rotate)

    def route_bitcell(self):
        """wordline driver wordline to bitcell array wordlines"""
        debug.info(1, "Route bitcells")
        for row in range(self.num_rows):
            wl_in = self.bitcell_array_inst.get_pin("wl[{}]".format(row))
            driver_out = self.wordline_driver_inst.get_pin("wl[{0}]".format(row))
            self.add_rect(wl_in.layer, offset=vector(driver_out.rx(), wl_in.by()),
                          width=wl_in.lx() - driver_out.rx(), height=wl_in.height())
        self.route_bitcell_array_power()

    def route_bitcell_array_power(self):
        self.route_all_instance_power(self.bitcell_array_inst)

    def join_rects(self, top_rects, top_layer, bottom_rects, bottom_layer, via_alignment,
                   y_shift=0, rect_align=JOIN_TOP_ALIGN):
        vias, _, fill_layers = contact.get_layer_vias(bottom_layer,
                                                      top_layer,
                                                      cross_via=False)
        fill_widths, fill_heights, via_extensions = [], [], []
        for via, fill_layer in zip(vias[1:], fill_layers):
            fill_height, fill_width = self.calculate_min_area_fill(via.height, layer=fill_layer)
            fill_heights.append(fill_height)
            fill_widths.append(fill_width)
            via_extensions.append(self.get_drc_by_layer(fill_layer, "wide_metal_via_extension")
                                  or 0.0)

        for bottom_rect, top_rect in zip(bottom_rects, top_rects):
            if top_rect.by() + y_shift > bottom_rect.uy():
                if rect_align == JOIN_BOT_ALIGN:
                    rect_width = bottom_rect.rx() - bottom_rect.lx()
                    x_offset = bottom_rect.lx()
                else:
                    rect_width = min(bottom_rect.rx() - bottom_rect.lx(),
                                     top_rect.rx() - top_rect.lx())
                    x_offset = top_rect.cx() - 0.5 * rect_width

                height = top_rect.by() - bottom_rect.uy() + y_shift
                if vias:
                    height += vias[0].height
                self.add_rect(bottom_layer, offset=vector(x_offset,
                                                          bottom_rect.uy()),
                              width=rect_width, height=height)
            if not vias:
                continue
            for via in vias:
                if rect_align == JOIN_BOT_ALIGN:
                    via_x = bottom_rect.cx()
                else:
                    via_x = top_rect.cx()
                via_mid = vector(via_x, top_rect.by() + 0.5 * via.height + y_shift)
                self.add_contact_center(via.layer_stack, offset=via_mid)

            for fill_layer, fill_width, fill_height, via_extension \
                    in zip(fill_layers, fill_widths, fill_heights, via_extensions):
                if rect_align == JOIN_BOT_ALIGN:
                    reference_rect = bottom_rect
                else:
                    reference_rect = top_rect
                if via_alignment == LEFT_FILL:
                    x_offset = reference_rect.lx() - via_extension
                elif via_alignment == MID_FILL:
                    x_offset = reference_rect.cx() - 0.5 * fill_width
                else:
                    x_offset = reference_rect.rx() + via_extension - fill_width
                self.add_rect(fill_layer, offset=vector(x_offset, top_rect.by() + y_shift),
                              width=fill_width, height=fill_height)

    def join_bitlines(self, top_instance, top_suffix, bottom_instance,
                      bottom_suffix, word_size=None, y_shift=0, rect_align=JOIN_TOP_ALIGN):
        """Join bitlines using given 'top_instance' and 'bottom_instance
        Pin names are extracted by adding 'top/bottom_suffix to 'bl' and 'br'
        bl fill is aligned to the left and br fill is aligned to the right"""
        if word_size is None:
            word_size = self.word_size
        pin_names = ["bl", "br"]
        alignments = [LEFT_FILL, RIGHT_FILL]
        for i in range(2):
            pin_name, alignment = pin_names[i], alignments[i]
            top_pins = [top_instance.get_pin("{}{}[{}]".format(pin_name, top_suffix, i))
                        for i in range(word_size)]
            bottom_pins = [bottom_instance.get_pin("{}{}[{}]".format(pin_name, bottom_suffix, i))
                           for i in range(word_size)]
            self.join_rects(top_pins, top_pins[0].layer, bottom_pins, bottom_pins[0].layer,
                            alignment, y_shift=y_shift, rect_align=rect_align)

    def get_closest_bitline_pin(self, x_offset, pin_name):
        """Get closest bitline pin (bl/br) to x_offset"""
        mid_x_offsets = [x + 0.5 * self.bitcell.width for x in
                         self.bitcell_array.bitcell_offsets]
        bitcell_array_col = min(range(self.num_cols),
                                key=lambda col: abs(x_offset - mid_x_offsets[col]))

        return self.bitcell_array_inst.get_pin("{}[{}]".format(pin_name, bitcell_array_col))

    def route_precharge(self):
        """precharge bitlines to bitcell bitlines
            col_mux or sense amp bitlines to precharge bitlines"""
        debug.info(1, "Route Precharge")
        self.join_bitlines(top_instance=self.bitcell_array_inst, top_suffix="",
                           bottom_instance=self.precharge_array_inst,
                           bottom_suffix="", word_size=self.num_cols)

        self.route_all_instance_power(self.precharge_array_inst)

        if self.col_mux_array_inst is not None:
            self.join_bitlines(top_instance=self.precharge_array_inst, top_suffix="",
                               bottom_instance=self.col_mux_array_inst,
                               bottom_suffix="", word_size=self.num_cols)
        else:
            precharge_bl = self.precharge_array_inst.get_pin("bl[0]")
            sense_bl = self.sense_amp_array_inst.get_pin("bl[0]")

            vias, _, fill_layers = contact.get_layer_vias(sense_bl.layer,
                                                          METAL2,
                                                          cross_via=False)

            if sense_bl.lx() == precharge_bl.lx() or not vias:
                rect_align = JOIN_TOP_ALIGN
            else:
                rect_align = JOIN_BOT_ALIGN
            self.join_bitlines(top_instance=self.precharge_array_inst, top_suffix="",
                               bottom_instance=self.sense_amp_array_inst,
                               bottom_suffix="", rect_align=rect_align)

    def route_column_mux(self):
        """Column mux power and copy sel pins, connect sense amp and col mux bitlines"""
        debug.info(1, "Route column mux")
        if self.col_mux_array_inst is None:
            return
        for i in range(self.words_per_row):
            self.copy_layout_pin(self.col_mux_array_inst, "sel[{}]".format(i))

        self.join_bitlines(top_instance=self.col_mux_array_inst, top_suffix="_out",
                           bottom_instance=self.sense_amp_array_inst,
                           bottom_suffix="", y_shift=self.get_parallel_space(METAL1),
                           rect_align=JOIN_BOT_ALIGN)

        self.route_all_instance_power(self.col_mux_array_inst)

    def route_sense_amp(self):
        """Routes sense amp power and connects write driver bitlines to sense amp bitlines"""
        debug.info(1, "Route sense amp")
        self.route_all_instance_power(self.sense_amp_array_inst)
        # write driver to sense amp
        self.join_bitlines(top_instance=self.sense_amp_array_inst, top_suffix="",
                           bottom_instance=self.write_driver_array_inst,
                           bottom_suffix="")

    def get_m2_m3_below_instance(self, inst, index=0):
        """Get location below instance where we can insert m2m3 vias.
        Index=0 is closest, separate by index*via pitch for index greater than 0"""
        # lowest using child mod
        # find first instance with connections > 2 (vdd, gnd), this should be the reference model
        inst_mod = inst.mod
        child_inst = next(inst_mod.insts[i] for i in range(len(inst_mod.insts)) if len(inst_mod.conns[i]) > 2)
        child_mod = child_inst.mod
        m2_m3 = (child_mod.get_layer_shapes(METAL2, recursive=True) +
                 child_mod.get_layer_shapes(METAL3, recursive=True))
        lowest_m2_m3 = min(m2_m3, key=lambda x: x.by())
        y_offset = inst.by() + child_inst.by() + lowest_m2_m3.by()
        # lowest using shallow m2/m3
        m2_m3 = (inst_mod.get_layer_shapes(METAL2, recursive=False) +
                 inst_mod.get_layer_shapes(METAL3, recursive=False))
        if m2_m3:
            lowest_m2_m3 = min(m2_m3, key=lambda x: x.by())
            y_offset = min(y_offset, inst.by() + lowest_m2_m3.by())

        via_height = max(m2m3.height, m3m4.height)
        metal_space = self.get_line_end_space(METAL3)
        if index > 0:
            metal_space = max(metal_space, self.get_line_end_space(METAL4))
        return y_offset - (1 + index) * (metal_space + via_height)

    def route_write_driver_data_bar(self, word):
        """data flop dout_bar to write driver in"""
        flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(word))
        driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(word))

        if flop_pin.layer == METAL2 and driver_pin.layer == METAL2:
            self.add_rect(METAL2, offset=flop_pin.ul(), width=flop_pin.width(),
                          height=driver_pin.by() - flop_pin.uy() + self.m2_width)
            self.add_rect(METAL2, offset=vector(driver_pin.cx(), driver_pin.by()),
                          width=flop_pin.cx() - driver_pin.cx())
        else:
            m2_rect = self.add_rect(METAL2, offset=flop_pin.ul(),
                                    height=driver_pin.by() - flop_pin.uy())
            self.join_rects([driver_pin], driver_pin.layer, [m2_rect], METAL2,
                            via_alignment=RIGHT_FILL)

    def route_write_driver_data(self, word, flop_pin, driver_pin, y_bend):
        """data flop dout to write driver in"""

        self.add_rect(METAL2, offset=flop_pin.ul(), width=flop_pin.width(),
                      height=y_bend - flop_pin.uy() + self.m2_width)

        offset = vector(driver_pin.lx(), y_bend)
        self.add_rect(METAL2, offset=offset, width=flop_pin.rx() - offset.x)
        m2_rect = self.add_rect(METAL2, offset=offset, height=driver_pin.by() - offset.y)
        self.join_rects([driver_pin], driver_pin.layer, [m2_rect], METAL2,
                        via_alignment=LEFT_FILL)

    def route_write_driver_mask_in(self, word, mask_flop_out_via_y, mask_driver_in_via_y):
        """mask flop output to write driver in"""

        flop_pin = self.get_mask_flop_out(word)

        # align with sense amp bitline

        br_pin = self.sense_amp_array_inst.get_pin("br[{}]".format(word))
        br_x_offset = self.sense_amp_array_inst.get_pin("br[{}]".format(word)).lx()

        driver_pin = self.get_write_driver_mask_in(word)
        self.add_rect(METAL2, offset=flop_pin.ul(), width=flop_pin.width(),
                      height=mask_flop_out_via_y + self.m2_width - flop_pin.uy())
        self.add_contact(m2m3.layer_stack, offset=vector(flop_pin.lx(), mask_flop_out_via_y))

        # add via to m4
        via_offset = vector(br_x_offset, mask_flop_out_via_y)
        cont = self.add_contact(m3m4.layer_stack, offset=via_offset)
        self.join_pins_with_m3(cont, flop_pin, cont.cy())

        # m4 to below write driver
        self.add_rect(METAL4, offset=via_offset, height=mask_driver_in_via_y - via_offset.y)
        # m3 to driver in
        self.add_contact(m3m4.layer_stack,
                         offset=vector(br_x_offset, mask_driver_in_via_y))
        offset = vector(driver_pin.lx(), mask_driver_in_via_y)
        self.add_rect(METAL3, offset=offset, width=br_pin.cx() - driver_pin.lx(),
                      height=m3m4.height)
        self.add_rect(METAL2, offset=vector(driver_pin.lx(), offset.y),
                      width=driver_pin.width(),
                      height=driver_pin.by() - offset.y)
        self.add_contact(m2m3.layer_stack, offset=offset)

    def route_write_driver(self):
        """Route mask, data and data_bar from flops to write driver"""
        debug.info(1, "Route write driver")
        flop = self.msf_data_in.child_mod
        m2_rects = flop.get_layer_shapes(METAL2)
        top_out_pin_y = max([flop.get_pin("dout"), flop.get_pin("dout_bar")],
                            key=lambda x: x.uy()).uy()
        valid_m2 = [x.uy() for x in m2_rects if x.uy() < top_out_pin_y]
        max_obstruction_y = max(valid_m2)
        y_bend = max(top_out_pin_y - self.m2_width, max_obstruction_y +
                     self.get_line_end_space(METAL2))
        y_bend += self.data_in_flops_inst.by()

        mask_flop_out_via_y = self.get_m2_m3_below_instance(self.data_in_flops_inst, 0)
        mask_driver_in_via_y = self.get_m2_m3_below_instance(self.write_driver_array_inst, 0)

        pin_combinations = [("dout", "data"), ("dout_bar", "data_bar")]

        for word in range(0, self.word_size):
            for flop_name, driver_name in pin_combinations:
                flop_pin = self.data_in_flops_inst.get_pin("{}[{}]".format(flop_name, word))
                driver_pin = self.write_driver_array_inst. \
                    get_pin("{}[{}]".format(driver_name, word))
                self.route_write_driver_data(word, flop_pin, driver_pin, y_bend)
            if self.has_mask_in:
                self.route_write_driver_mask_in(word, mask_flop_out_via_y,
                                                mask_driver_in_via_y)

        self.route_all_instance_power(self.write_driver_array_inst)

    def get_write_driver_mask_in(self, word):
        """Get pin name for mask input. Either mask or mask_bar"""
        return self.write_driver_array_inst.get_pin("mask_bar[{}]".format(word))

    def get_mask_flop_out(self, word):
        pin_name = "dout" if "mask" in self.write_driver_array.child_mod.pins else "dout_bar"
        return self.mask_in_flops_inst.get_pin("{}[{}]".format(pin_name, word))

    def join_pins_with_m3(self, pin_a, pin_b, mid_y, min_fill_width=None, fill_height=None):
        """Join two pins using M3"""
        if fill_height is None:
            fill_height = m3m4.height
        if min_fill_width is None:
            fill_height, min_fill_width = self.calculate_min_area_fill(fill_height, layer=METAL3)

        fill_x = 0.5 * (pin_a.cx() + pin_b.cx())
        fill_width = max(min_fill_width, abs(pin_a.cx() - pin_b.cx()))
        self.add_rect_center(METAL3, offset=vector(fill_x, mid_y),
                             width=fill_width, height=fill_height)

    def route_flops(self):
        """Route input pins for mask flops and data flops"""
        fill_height = m3m4.height
        fill_height, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL3)

        if self.has_mask_in:
            self.route_all_instance_power(self.mask_in_flops_inst)
        self.route_all_instance_power(self.data_in_flops_inst)

        data_via_y = self.get_m2_m3_below_instance(self.data_in_flops_inst, 1)
        mask_via_y = self.get_m2_m3_below_instance(self.mask_in_flops_inst, 1)

        for word in range(self.word_size):
            # align data flop in with br
            data_in = self.data_in_flops_inst.get_pin("din[{}]".format(word))
            y_offset = data_via_y
            x_offset = data_in.lx()
            offset = vector(x_offset, y_offset)
            self.add_rect(METAL2, offset=offset, height=data_in.by() - y_offset)
            cont = self.add_contact(m2m3.layer_stack, offset=offset)
            br_pin = self.sense_amp_array_inst.get_pin("br[{}]".format(word))
            x_offset = br_pin.lx()
            self.join_pins_with_m3(cont, br_pin, cont.cy(), fill_width, fill_height)

            self.add_contact(m3m4.layer_stack, offset=vector(x_offset, y_offset))

            self.add_layout_pin("DATA[{}]".format(word), METAL4,
                                offset=vector(x_offset, self.min_point),
                                height=y_offset - self.min_point)
            if not self.has_mask_in:
                continue
            # align mask flop in with bl
            mask_in = self.mask_in_flops_inst.get_pin("din[{}]".format(word))
            bl_pin = self.sense_amp_array_inst.get_pin("bl[{}]".format(word))
            y_offset = mask_via_y

            self.add_rect(METAL2, offset=vector(mask_in.lx(), mask_via_y),
                          height=mask_in.by() - mask_via_y)
            via_offset = vector(mask_in.lx(), y_offset)
            cont = self.add_contact(m2m3.layer_stack, offset=via_offset)
            self.join_pins_with_m3(cont, bl_pin, cont.cy(), fill_width, fill_height)

            via_offset = vector(bl_pin.lx(), y_offset)
            self.add_contact(m3m4.layer_stack, offset=via_offset)
            self.add_layout_pin("MASK[{}]".format(word), METAL4,
                                offset=vector(via_offset.x, self.min_point),
                                height=via_offset.y - self.min_point)

    def route_tri_gate(self):
        """Route sense amp data output to tri-state in, tri-state in to DATA (in)"""
        debug.info(1, "Route tri state array")
        self.route_all_instance_power(self.tri_gate_array_inst)

        if self.has_mask_in:
            top_inst = self.mask_in_flops_inst
        else:
            top_inst = self.data_in_flops_inst

        if "in_bar" in self.tri_gate_array.child_mod.pins:
            sense_pin_name, tri_pin_name = "dout_bar[{}]", "in_bar[{}]"
        else:
            sense_pin_name, tri_pin_name = "dout[{}]", "in[{}]"

        tri_in_via_y = self.get_m2_m3_below_instance(top_inst, 0)
        sense_out_y = self.get_m2_m3_below_instance(self.sense_amp_array_inst, 0)

        fill_height = m3m4.height
        fill_height, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL3)

        for word in range(self.word_size):
            tri_in = self.tri_gate_array_inst.get_pin(tri_pin_name.format(word))
            bl_pin = self.sense_amp_array_inst.get_pin("bl[{}]".format(word))
            # tri input to align with bl
            y_offset = tri_in_via_y
            x_offset = bl_pin.lx()
            self.add_rect(METAL2, offset=tri_in.ul(), height=y_offset - tri_in.uy())
            cont = self.add_contact(m2m3.layer_stack, offset=vector(tri_in.lx(), y_offset))

            self.join_pins_with_m3(cont, bl_pin, cont.cy(), fill_width, fill_height)
            self.add_contact_center(m3m4.layer_stack, offset=vector(bl_pin.cx(),
                                                                    cont.cy()))
            self.add_rect(METAL4, offset=vector(x_offset, y_offset),
                          height=sense_out_y - y_offset + m3m4.height,
                          width=bl_pin.width())
            # sense_out_y to sense amp out
            sense_out = self.sense_amp_array_inst.get_pin(sense_pin_name.format(word))
            via_y = sense_out_y + 0.5 * m3m4.height
            cont = self.add_contact_center(m3m4.layer_stack, offset=vector(bl_pin.cx(), via_y))
            self.join_pins_with_m3(cont, sense_out, cont.cy(), fill_width, fill_height)
            self.add_contact_center(m2m3.layer_stack, offset=vector(sense_out.cx(), via_y))
            self.add_rect(METAL2, offset=vector(sense_out.lx(), sense_out_y),
                          width=sense_out.width(),
                          height=sense_out.by() - sense_out_y)

            # tri output to data pin
            tri_out_pin = self.tri_gate_array_inst.get_pin("out[{}]".format(word))
            data_pin = self.get_pin("DATA[{}]".format(word))

            via_y = tri_out_pin.by() + 0.5 * m2m3.height
            cont = self.add_contact_center(m2m3.layer_stack, offset=vector(tri_out_pin.cx(), via_y))
            self.join_pins_with_m3(cont, data_pin, cont.cy(), fill_width, fill_height)
            self.add_contact_center(m3m4.layer_stack, offset=vector(data_pin.cx(), via_y))

    def route_control_buffers(self):
        """Route output of control flops to control logic buffers.
         Also route non-flop inputs to control logic buffers"""
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
        _, fill_height = self.calculate_min_area_fill(rail_height, layer=METAL2)
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

            if control_pin.cy() > y_offset:
                height = max(control_pin.cy() - y_offset, fill_height)
            else:
                height = min(control_pin.cy() - y_offset, -fill_height)
            self.add_rect(METAL2, offset=vector(mid_x - 0.5 * rail_height, y_offset),
                          width=rail_height, height=height)
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

    def route_control_flops_power(self):
        """connect bank_sel and read flops power pins to control_buffers and/or tri-state power pins"""
        # check if direct power connection is possible
        if (self.read_buf_inst.uy() + self.rail_height +
                self.get_parallel_space(METAL1) < self.control_buffers_inst.by()):
            for i in range(2):
                pin_name, rail = ["vdd", "gnd"][i], [self.mid_vdd, self.mid_gnd][i]
                pins = self.read_buf_inst.get_pins(pin_name) + self.bank_sel_buf_inst.get_pins(pin_name)
                for pin in pins:
                    self.add_rect(pin.layer, pin.lr(), width=rail.cx() - pin.rx(), height=pin.height())
            self.route_all_instance_power(self.read_buf_inst)
            self.route_all_instance_power(self.bank_sel_buf_inst)
            return

            # destination ground pins
        control_buffers_gnd = self.control_buffers_inst.get_pins("gnd")
        if len(control_buffers_gnd) == 1:
            bottom_gnd = control_buffers_gnd[0]
            top_gnd = min(self.tri_gate_array_inst.get_pins("gnd"), key=lambda x: x.cy())
        else:
            bottom_gnd, top_gnd = sorted(control_buffers_gnd, key=lambda x: x.cy())

        control_vdd_pins = self.control_buffers_inst.get_pins("vdd")
        if len(control_vdd_pins) == 1:
            mid_vdd = control_vdd_pins[0].cy()
        else:
            mid_vdd = 0.5 * (bottom_gnd.cy() + top_gnd.cy())

        y_offsets = [top_gnd.cy(), mid_vdd, bottom_gnd.cy()]
        # destination pins
        destination_pins = [self.mid_gnd, self.mid_vdd, self.mid_gnd]
        pins = [self.read_buf_inst.get_pin("gnd"),
                self.bank_sel_buf_inst.get_pin("vdd"),
                self.bank_sel_buf_inst.get_pin("gnd")]

        non_flop_input_pins = [self.get_pin(x) for x in self.get_non_flop_control_inputs()]
        x_start = max(non_flop_input_pins, key=lambda x: x.lx()).lx()
        pitch = bottom_gnd.height() + self.get_wide_space(METAL1)

        if y_offsets[1] >= pins[1].cy():  # going up
            indices = range(3)
        else:
            indices = reversed(range(3))

        x_offset = x_start

        for i in indices:
            start_pin = pins[i]
            destination_y = y_offsets[i]
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
            if len(control_vdd_pins) == 2 and i == 1:
                self.add_power_via(rect, self.mid_vdd)
            x_offset += pitch

    def route_control_flops(self):
        """Route control flop inputs (clk, din) and connect clk to control logic buffers"""
        debug.info(1, "Route control flops")
        self.route_control_flops_power()
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
                if in_pin_name == "clk":
                    layer = METAL2
                else:
                    layer = METAL3
                    self.add_cross_contact_center(cross_m2m3,
                                                  offset=vector(x_offset + 0.5 * self.bus_width,
                                                                input_pin.cy()))
                    self.add_contact(m2m3.layer_stack, offset=input_pin.ll(), rotate=90)
                height = self.get_min_layer_width(layer)
                self.add_rect(layer, offset=vector(x_offset, input_pin.cy() - 0.5 * height),
                              width=input_pin.lx() - x_offset, height=height)

                if input_pin.layer == METAL1:
                    self.add_contact(m1m2.layer_stack,
                                     offset=vector(input_pin.lx(),
                                                   input_pin.cy() - 0.5 * m1m2.width),
                                     rotate=90)

        # clk to control_buffer
        clk_pin = self.get_pin("clk")
        non_flop_pins = [self.get_pin(x) for x in self.get_non_flop_control_inputs()]
        right_most_pin = max(non_flop_pins, key=lambda x: x.rx())
        rail_x = right_most_pin.lx() + self.bus_pitch
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

    def get_wordline_power_x_offset(self):
        """ x offset to start power rail to mid power rails"""
        return self.wordline_driver_inst.rx()

    def route_wordline_in(self):
        for i in range(self.num_rows):
            self.copy_layout_pin(self.wordline_driver_inst, "in[{0}]".format(i),
                                 "dec_out[{0}]".format(i))

    def route_wordline_driver(self):
        """wordline driver out to bitcell wl in + wordline_enable route"""
        debug.info(1, "Route wordline driver")
        self.route_wordline_in()
        self.join_wordline_bitcell_nwell()
        # route enable signal
        en_pin = self.wordline_driver_inst.get_pin("en")
        en_rail = self.wordline_en_rail
        y_offset = en_pin.by() - 0.5 * self.bus_width

        self.add_rect(METAL2, offset=en_rail.ul(), height=y_offset - en_rail.uy(), width=self.bus_width)
        self.add_cross_contact_center(cross_m2m3, offset=vector(en_rail.cx(), y_offset))
        self.add_rect(METAL3, offset=vector(en_pin.lx(), y_offset - 0.5 * self.bus_width),
                      width=en_rail.rx() - en_pin.lx(), height=self.bus_width)
        self.add_cross_contact_center(cross_m2m3, offset=vector(en_pin.cx(), y_offset))

        if OPTS.separate_vdd:
            self.copy_layout_pin(self.wordline_driver_inst, "vdd", "vdd_wordline")

        if OPTS.separate_vdd:
            pin_end = [self.bitcell_array_inst.lx(), self.wordline_driver_inst.rx()]
        else:
            pin_end = [self.bitcell_array_inst.lx(), self.bitcell_array_inst.rx()]

        pin_names = ["gnd", "vdd"]
        x_offset = self.get_wordline_power_x_offset()
        for i in range(2):
            pin_name = pin_names[i]
            bitcell_pins = self.bitcell.get_pins(pin_names[i])
            bitcell_pins = [x for x in bitcell_pins if x.layer == METAL1]
            sample_bitcell_pin = min(bitcell_pins, key=lambda x: x.height())
            for pin in self.wordline_driver_inst.get_pins(pin_name):
                pin_height = min(sample_bitcell_pin.height(), pin.height())
                self.add_rect(pin.layer, offset=vector(x_offset, pin.cy() - 0.5 * pin_height),
                              height=pin_height,
                              width=pin_end[i] - x_offset)

    def join_wordline_bitcell_nwell(self):
        wordline_inverter = self.wordline_driver.logic_buffer.buffer_mod.buffer_invs[-1]
        layers = [NWELL]
        purposes = [DRAWING]
        if self.has_pwell:
            layers.append(PWELL)
            purposes.append(DRAWING)
        rects = create_wells_and_implants_fills(wordline_inverter,
                                                self.bitcell, layers=layers,
                                                purposes=purposes)
        bitcell_nwell = max(self.bitcell.get_layer_shapes(NWELL), key=lambda x: x.height * x.width)
        wordline_nwell = max(wordline_inverter.get_layer_shapes(NWELL), key=lambda x: x.height * x.width)
        x_offset = self.wordline_driver_inst.rx()
        width = self.bitcell_array_inst.get_pin("bl[0]").lx() - x_offset
        for row in range(self.num_rows):
            y_base = self.bitcell_array_inst.by() + row * self.bitcell.height
            for layer, rect_bottom, rect_top, _, _ in rects:
                # cover align with bitcell nwell
                if row in [0, self.num_rows - 1]:
                    if layer == PWELL:
                        continue
                    rect_top = max(bitcell_nwell.uy(), wordline_nwell.uy())

                if (row % 2 == 0 and layer == NWELL) or (row % 2 == 0 and layer == PWELL):
                    y_offset = y_base + (self.bitcell.height - rect_top)
                else:
                    y_offset = y_base + rect_bottom
                self.add_rect(layer, offset=vector(x_offset, y_offset), width=width,
                              height=rect_top - rect_bottom)

    def route_gnd_pin(self, pin, add_via=True, via_rotate=90):
        self.add_rect(pin.layer, offset=vector(self.mid_gnd.lx(), pin.by()),
                      width=self.right_gnd.rx() - self.mid_gnd.lx(), height=pin.height())
        if add_via:
            self.add_power_via(pin, self.mid_gnd, via_rotate)

    def route_vdd_pin(self, pin, add_via=True, via_rotate=90):
        self.add_rect(pin.layer, offset=vector(self.mid_vdd.lx(), pin.by()),
                      width=self.right_vdd.rx() - self.mid_vdd.lx(), height=pin.height())
        if add_via:
            self.add_power_via(pin, self.mid_vdd, via_rotate=via_rotate)
            self.add_power_via(pin, self.right_vdd, via_rotate=via_rotate)

    def add_power_via(self, pin, power_pin, via_rotate=90, via_size=None):
        if via_size is None:
            via_size = [1, 2]
        if hasattr(pin, "layer") and pin.layer == METAL1 and power_pin.layer == METAL1:
            return
        if hasattr(pin, "layer") and pin.layer == METAL3:
            via = m2m3
            if power_pin.layer == METAL1:
                m2_via = self.add_contact_center(m1m2.layer_stack,
                                                 offset=vector(power_pin.cx(), pin.cy()),
                                                 size=via_size, rotate=via_rotate)
                fill_width = power_pin.width()
                min_height = m2_via.height if via_rotate == 0 else m2_via.width
                _, fill_height = self.calculate_min_area_fill(fill_width, min_height=min_height,
                                                              layer=METAL2)
                self.add_rect_center(METAL2, offset=vector(power_pin.cx(), pin.cy()),
                                     width=fill_width, height=fill_height)

        else:
            via = m1m2
        self.add_contact_center(via.layer_stack, offset=vector(power_pin.cx(), pin.cy()),
                                size=via_size, rotate=via_rotate)

    def get_all_power_instances(self):
        instances = [self.wordline_driver_inst, self.precharge_array_inst, self.sense_amp_array_inst,
                     self.write_driver_array_inst, self.data_in_flops_inst, self.mask_in_flops_inst,
                     self.tri_gate_array_inst]
        if self.col_mux_array_inst is not None:
            instances.append(self.col_mux_array_inst)
        return instances

    def get_all_power_pins(self):
        """All power pins except bitcell"""
        instances = self.get_all_power_instances()

        def get_power_pins(inst):
            results = inst.get_pins("vdd") if "vdd" in inst.mod.pins else []
            results += inst.get_pins("gnd") if "gnd" in inst.mod.pins else []
            return results

        all_power_pins = []
        for inst_ in instances:
            all_power_pins.extend(get_power_pins(inst_))
        return all_power_pins

    def add_m2m4_power_rails_vias(self):
        all_power_pins = sorted(self.get_all_power_pins(), key=lambda x: x.name)
        power_groups = {k: list(v) for k, v in itertools.groupby(all_power_pins,
                                                                 key=lambda x: x.name)}
        fill_width = self.mid_gnd.width()
        fill_width, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL3)
        for rail in [self.mid_vdd, self.right_vdd, self.mid_gnd, self.right_gnd]:
            self.add_layout_pin(rail.name, METAL4, offset=rail.ll(), width=rail.width(),
                                height=rail.height())
            for pin_name, pins in power_groups.items():
                if not pin_name == rail.name:
                    continue
                m3_pins = [x for x in pins if x.layer == METAL3]
                m3_pin_y = set(map(lambda x: x.cy(), m3_pins))
                all_pin_y = set(map(lambda x: x.cy(), pins))
                # only add m3 fill if no m3 vdd exists at that y offset
                m3_fill_y = all_pin_y.difference(m3_pin_y)
                m3_fill_y = [x for x in m3_fill_y if x > self.precharge_array_inst.by()]

                y_offsets = list(all_pin_y)
                for y_offset in y_offsets:
                    offset = vector(rail.cx(), y_offset)

                    if y_offset in m3_fill_y:
                        self.add_rect_center(METAL3, offset=offset, width=fill_width,
                                             height=fill_height)
                        vias = [m2m3, m3m4]
                    elif y_offset in m3_pin_y:
                        vias = [m3m4]
                    else:
                        vias = []
                    for via in vias:
                        self.add_contact_center(via.layer_stack,
                                                offset=offset, size=[1, 2], rotate=90)

    def get_m4_rail_x(self):
        """Gets position of middle m4 rail that goes across"""
        return 0.5 * self.bitcell.width

    def find_closest_unoccupied_index(self, index):
        """find closest unoccupied index greater than 'index'"""
        occupied = self.occupied_m4_bitcell_indices
        unoccupied = [x for x in range(self.num_cols) if x not in occupied and x > index]
        if not unoccupied:
            return None
        return unoccupied[min(range(len(unoccupied)), key=lambda i: abs(unoccupied[i] - index))]

    def route_body_tap_supplies(self):
        if not OPTS.use_body_taps:
            return
        rails = utils.get_libcell_pins(["vdd", "gnd"], OPTS.body_tap)
        if not rails["vdd"] or not rails["gnd"]:
            return

        rail_height = self.bitcell_array_inst.uy() - self.min_point
        for rail_name in ["vdd", "gnd"]:
            rail = rails[rail_name][0]
            for x_offset in self.bitcell_array.tap_offsets:
                pin_x = self.bitcell_array_inst.lx() + x_offset + rail.lx()
                pin = self.add_layout_pin(rail_name, METAL4, offset=vector(pin_x, self.min_point),
                                          width=rail.width(),
                                          height=rail_height)
                self.connect_control_buffers_power_to_grid(pin)

    def get_inter_array_power_grid_indices(self):
        """Using flop array, get spaces without instances. Mostly useful when words_per_row > 1"""
        cell_offsets = self.bitcell_array.bitcell_offsets

        mid_x_offsets = [x + 0.5 * self.bitcell.width for x in cell_offsets]
        # find actual flop instances
        flop_array = self.data_in_flops_inst.mod
        flop_instances = [flop_array.insts[i] for i in range(len(flop_array.conns))
                          if len(flop_array.conns[i]) > 2]
        # find empty spaces in flop array
        empty_offset_indices = list(set(range(len(cell_offsets))).difference(set(self.occupied_m4_bitcell_indices)))
        empty_offset_indices = list(sorted(empty_offset_indices))
        for i in empty_offset_indices.copy():
            for flop_instance in flop_instances:
                if flop_instance.lx() <= mid_x_offsets[i] <= flop_instance.rx():
                    empty_offset_indices.remove(i)
                    break

        cell_spacing = OPTS.bitcell_vdd_spacing
        # make a copy
        power_grid_indices = []

        if len(empty_offset_indices) == 0:
            i = 0
            while i < self.num_cols - 1:
                if i in self.occupied_m4_bitcell_indices:
                    index = self.find_closest_unoccupied_index(i)
                    i = max(index + 2, int(math.ceil(index / cell_spacing) * cell_spacing))
                else:
                    index = i
                    i += cell_spacing

                self.occupied_m4_bitcell_indices.append(index)
                power_grid_indices.append(index)
        else:
            debug.info(2, "Empty spaces: {}".format(empty_offset_indices))
            # group contiguous spaces
            empty_groups = [[empty_offset_indices[0]]]

            for empty_index in empty_offset_indices[1:]:
                if empty_index - empty_groups[-1][-1] == 1:
                    empty_groups[-1].append(empty_index)
                else:
                    empty_groups.append([empty_index])
            debug.info(2, "Empty spaces groups: {}".format(empty_groups))
            # find middle space
            empty_indices = [x[int(len(x) / 2)] for x in empty_groups]
            debug.info(2, "Empty middle offsets: {}".format(empty_indices))

            for i in range(cell_spacing, self.num_cols - 1, cell_spacing):
                closest_index = empty_indices[min(range(len(empty_indices)),
                                                  key=lambda x: abs(empty_indices[x] - i))]
                self.occupied_m4_bitcell_indices.append(closest_index)
                power_grid_indices.append(closest_index)

        debug.info(2, "Used cell indices: {}".format(power_grid_indices))
        return power_grid_indices, mid_x_offsets

    def get_inter_array_power_grid_offsets(self):
        """Find space to route power rails by looking for empty spaces in flop array
            If no empty space is found, just use original 'OPTS.bitcell_vdd_spacing'
            Otherwise, group empty spaces that are contiguous and choose the middle empty space
             closest to prediction by 'OPTS.bitcell_vdd_spacing'
        """
        rail_width = m3m4.height

        power_grid_indices, mid_x_offsets = self.get_inter_array_power_grid_indices()
        power_groups = {"vdd": [], "gnd": []}
        for index in power_grid_indices:
            mid_x = mid_x_offsets[index]
            power_groups["vdd"].append(mid_x - 0.5 * rail_width)
            closest_index = self.find_closest_unoccupied_index(index)
            if not closest_index:
                continue
            self.occupied_m4_bitcell_indices.append(closest_index)
            power_groups["gnd"].append(mid_x_offsets[closest_index] - 0.5 * rail_width)

        return power_groups

    def connect_control_buffers_power_to_grid(self, grid_pin):
        space = self.get_parallel_space(METAL3)
        forbidden = [(self.wordline_driver_inst.lx(), self.control_buffers_inst.rx())]
        if hasattr(self, "repeaters_insts"):
            forbidden.append((self.repeaters_insts[0].lx(), self.repeaters_insts[-1].rx()))
        connect_pin = True
        for (left, right) in forbidden:
            if left < grid_pin.rx() + space and right > grid_pin.lx() - space:
                connect_pin = False
        if connect_pin:
            control_power = self.control_buffers_inst.get_pins(grid_pin.name)
            for power_pin in control_power:
                offset = vector(grid_pin.cx(), power_pin.cy())
                for via in [m1m2, m2m3, m3m4]:
                    self.add_contact_center(via.layer_stack, offset=offset, rotate=90)
                for layer in [METAL2, METAL3]:
                    fill_height, fill_width = self.calculate_min_area_fill(power_pin.height(),
                                                                           layer=layer)
                    self.add_rect_center(layer, offset=offset, width=fill_width,
                                         height=fill_height)

    def route_intra_array_power_grid(self):
        """Add M4 rails along bitcell arrays columns"""
        debug.info(1, "Route intra-array power grid")

        all_power_pins = (self.get_all_power_pins() + self.bitcell_array_inst.get_pins("vdd") +
                          self.bitcell_array_inst.get_pins("gnd"))
        all_power_pins = sorted(all_power_pins, key=lambda x: x.name)
        all_power_pins = [x for x in all_power_pins if x.layer == METAL3]

        if not all_power_pins:
            return

        power_groups = {k: list(v) for k, v in itertools.groupby(all_power_pins,
                                                                 key=lambda x: x.name)}
        rail_width = m3m4.height
        rail_top = self.mid_vdd.uy()

        for pin_name, x_offsets in self.get_inter_array_power_grid_offsets().items():
            instance_power_pins = power_groups[pin_name]
            for base_offset in x_offsets:
                x_offset = base_offset + self.bitcell_array_inst.lx()
                new_pin = self.add_layout_pin(pin_name, METAL4,
                                              offset=vector(x_offset, self.min_point),
                                              width=rail_width, height=rail_top - self.min_point)
                for power_pin in instance_power_pins:
                    if new_pin.lx() > power_pin.lx() and new_pin.rx() < power_pin.rx():
                        self.add_contact_center(m3m4.layer_stack,
                                                offset=vector(new_pin.cx(), power_pin.cy()),
                                                rotate=90)
                self.connect_control_buffers_power_to_grid(new_pin)

    def fill_vertical_module_spaces(self):
        stack = [self.tri_gate_array_inst]
        if getattr(self, "mask_in_flops_inst", None):
            stack.append(self.mask_in_flops_inst)
        stack.extend([self.data_in_flops_inst, self.write_driver_array_inst,
                      self.sense_amp_array_inst])
        if getattr(self, "col_mux_array_inst", None):
            stack.append(self.col_mux_array_inst)
        stack.append(self.precharge_array_inst)
        for bottom_inst, top_inst in zip(stack[:-1], stack[1:]):
            join_vertical_adjacent_module_wells(self, bottom_inst, top_inst)

    def add_lvs_correspondence_points(self):
        # Add the bitline names
        for i in range(self.num_cols):
            bl_name = "bl[{}]".format(i)
            br_name = "br[{}]".format(i)
            bl_pin = self.bitcell_array_inst.get_pin(bl_name)
            br_pin = self.bitcell_array_inst.get_pin(br_name)
            self.add_label(text=bl_name,
                           layer=bl_pin.layer,
                           offset=bl_pin.ll())
            self.add_label(text=br_name,
                           layer=br_pin.layer,
                           offset=br_pin.ll())
