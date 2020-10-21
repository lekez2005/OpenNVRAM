from importlib import reload
from math import log

import debug
from base import utils
from base.contact import m2m3, m1m2, m3m4, contact
from base.contact_full_stack import ContactFullStack
from base.design import design
from base.vector import vector
from globals import OPTS
from modules.bitline_compute.bl_control_buffers_sense_trig import ControlBuffersSenseTrig
from modules.flop_buffer import FlopBuffer
from modules.buffer_stage import BufferStage
from modules.control_buffers import ControlBuffers
from modules.control_buffers_bank_mixin import ControlBuffersMixin
from pgates.pgate import pgate
from tech import delay_strategy_class
from tech import drc, power_grid_layers


class BaselineBank(design, ControlBuffersMixin):
    control_buffers = control_buffers_inst = data_in_flops_inst = write_driver_array_inst = None
    sense_amp_array_inst = None

    external_vdds = ["vdd_buffers", "vdd_data_flops", "vdd_wordline"]

    def __init__(self, word_size, num_words, words_per_row, num_banks=1, name=""):
        self.set_modules(self.get_module_list())

        if name == "":
            name = "bank_{0}_{1}".format(word_size, num_words)
        design.__init__(self, name)
        debug.info(2, "create bank of size {0} with {1} words".format(word_size, num_words))

        self.word_size = word_size
        self.num_words = num_words
        self.words_per_row = words_per_row
        self.num_banks = num_banks

        # The local control signals are gated when we have bank select logic,
        # so this prefix will be added to all of the input signals.
        self.prefix = "gated_"

        self.mirror_sense_amp = OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP

        self.compute_sizes()
        self.add_pins()
        self.create_modules()
        self.calculate_rail_offsets()
        self.add_modules()
        self.route_layout()
        self.calculate_dimensions()

        self.offset_all_coordinates()

    def set_modules(self, mod_list):
        for mod_name in mod_list:
            config_mod_name = getattr(OPTS, mod_name)
            class_file = reload(__import__(config_mod_name))
            mod_class = getattr(class_file, config_mod_name)
            setattr(self, "mod_"+mod_name, mod_class)

    @staticmethod
    def get_module_list():
        return ["tri_gate", "bitcell", "decoder", "ms_flop_array", "ms_flop_array_horizontal", "wordline_driver",
                "bitcell_array", "sense_amp_array", "precharge_array",
                "column_mux_array", "write_driver_array", "tri_gate_array"]

    def calculate_dimensions(self):
        self.width = self.bitcell_array_inst.rx() - self.row_decoder_inst.lx()
        self.height = self.row_decoder_inst.uy() - min(self.row_decoder_inst.by(), self.control_buffers_inst.by())

    def add_modules(self):
        self.add_control_buffers()
        self.add_read_flop()

        self.add_tri_gate_array()
        self.add_data_mask_flops()
        self.add_write_driver_array()
        self.add_sense_amp_array()
        self.add_precharge_array()
        self.add_bitcell_array()

        self.add_control_rails()

        self.add_wordline_driver()
        self.add_row_decoder()

        self.add_vdd_gnd_rails()

    def route_layout(self):
        self.connect_buffer_rails()
        self.route_control_buffer()
        self.route_read_buf()
        self.route_precharge()
        self.route_sense_amp()
        self.route_bitcell()
        self.route_write_driver()
        self.route_flops()
        self.route_tri_gate()
        self.route_wordline_driver()

        self.route_decoder()
        self.route_wordline_in()

        self.calculate_rail_vias()  # horizontal rail vias

        self.add_decoder_power_vias()
        self.add_right_rails_vias()

        self.route_body_tap_supplies()
        self.route_control_buffers_power()

    def add_pins(self):
        """ Adding pins for Bank module"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))

        if self.mirror_sense_amp:
            control_pins = ["bank_sel", "read", "clk", "vdd", "gnd"]
        else:
            control_pins = ["bank_sel", "read", "clk", "sense_trig", "vdd", "gnd"]
        for pin in control_pins:
            self.add_pin(pin)

        if OPTS.separate_vdd:
            self.add_pin_list(self.external_vdds)
        if self.mirror_sense_amp and OPTS.sense_trigger_delay > 0:
            self.add_pin("sense_trig")

    def get_module_exceptions(self):
        return []

    def create_modules(self):

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

        # run optimizations

        run_optimizations = hasattr(OPTS, 'run_optimizations') and OPTS.run_optimizations
        if hasattr(OPTS, 'configure_sizes'):
            getattr(OPTS, 'configure_sizes')(self, OPTS)
        if run_optimizations:

            delay_strategy = delay_strategy_class()(self)

            OPTS.clk_buffers = delay_strategy.get_clk_buffer_sizes()

            OPTS.wordline_buffers = delay_strategy.get_wordline_driver_sizes()

            self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows,
                                                      buffer_stages=OPTS.wordline_buffers)
            if self.wordline_driver:
                OPTS.wordline_en_buffers = delay_strategy.get_wordline_en_sizes()

            OPTS.write_buffers = delay_strategy.get_write_en_sizes()

            OPTS.sense_amp_buffers = delay_strategy.get_sense_en_sizes()

            precharge_sizes = delay_strategy.get_precharge_sizes()
            OPTS.precharge_buffers = precharge_sizes[:-1]
            OPTS.precharge_size = precharge_sizes[-1]

            predecode_sizes = delay_strategy.get_predecoder_sizes()
            OPTS.predecode_sizes = predecode_sizes[1:]
        else:
            self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows,
                                                      buffer_stages=OPTS.wordline_buffers)
        # assert False

        self.precharge_array = self.create_module('precharge_array', columns=self.num_cols, size=OPTS.precharge_size)

        self.create_control_buffers()

        self.decoder = self.create_module('decoder', rows=self.num_rows)

        self.control_flop = FlopBuffer(OPTS.control_flop, OPTS.control_flop_buffers)
        self.add_mod(self.control_flop)

        self.m9m10 = ContactFullStack(start_layer=8, stop_layer=-1, centralize=False)

    def create_module(self, mod_name, *args, **kwargs):
        if mod_name not in self.get_module_list():
            return
        mod = getattr(self, 'mod_' + mod_name)(*args, **kwargs)
        self.add_mod(mod)
        return mod

    def compute_sizes(self):
        """  Computes the required sizes to create the bank """

        self.num_cols = int(self.words_per_row*self.word_size)
        self.num_rows = int(self.num_words / self.words_per_row)

        self.row_addr_size = int(log(self.num_rows, 2))
        self.col_addr_size = int(log(self.words_per_row, 2))
        self.addr_size = self.col_addr_size + self.row_addr_size

        debug.check(self.num_rows*self.num_cols==self.word_size*self.num_words,"Invalid bank sizes.")
        debug.check(self.addr_size==self.col_addr_size + self.row_addr_size,"Invalid address break down.")

        # Width for left gnd rail
        self.vdd_rail_width = 5*self.m2_width
        self.gnd_rail_width = 5*self.m2_width

        # m2 fill width for m1-m3 via
        min_area = drc["minarea_metal1_contact"]
        self.via_m2_fill_height = m1m2.second_layer_height
        self.via_m2_fill_width = utils.ceil(min_area/self.via_m2_fill_height)

        # Number of control lines in the bus
        self.num_control_lines = 6
        # The order of the control signals on the control bus:
        self.input_control_signals = ["clk_buf", "tri_en", "w_en", "s_en"]
        self.control_signals = list(map(lambda x: self.prefix + x,
                                        ["s_en", "clk_bar", "clk_buf", "tri_en_bar", "tri_en", "w_en"]))

        # The central bus is the column address (both polarities), row address
        self.num_addr_lines = self.row_addr_size

        # M1/M2 routing pitch is based on contacted pitch
        self.m1_pitch = m1m2.width + self.get_parallel_space("metal1")
        self.m2_pitch = m2m3.width + self.get_parallel_space("metal2")
        self.m3_pitch = m2m3.width + self.get_parallel_space("metal3")

        # Overall central bus gap. It includes all the column mux lines,
        # control lines, address flop to decoder lines and a GND power rail in M2
        # 1.5 pitches on the right on the right of the control lines for vias (e.g. column mux addr lines)
        self.start_of_right_central_bus = -self.m2_pitch * (self.num_control_lines + 1.5)
        # one pitch on the right on the addr lines and one on the right of the gnd rail

        self.gnd_x_offset = self.start_of_right_central_bus - self.gnd_rail_width - self.m2_pitch

        self.start_of_left_central_bus = self.gnd_x_offset - self.m2_pitch*(self.num_addr_lines+1)
        # add a pitch on each end and around the gnd rail
        self.overall_central_bus_width = - self.start_of_left_central_bus + self.m2_width

    def get_wordline_in_net(self):
        return "dec_out[{}]"

    def get_enable_names(self):
        return []

    def create_control_buffers(self):
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            if OPTS.sense_trigger_delay > 0:
                self.control_buffers = ControlBuffersSenseTrig()
            else:
                self.control_buffers = ControlBuffers()
        else:
            if OPTS.baseline:
                from modules.baseline_latched_control_buffers import LatchedControlBuffers
            else:
                from modules.bitline_compute.bl_latched_control_buffers import LatchedControlBuffers
            self.control_buffers = LatchedControlBuffers()
        self.add_mod(self.control_buffers)

    def get_control_names(self):
        if self.mirror_sense_amp:
            return ["precharge_en_bar", "write_en_bar", "write_en", "clk_bar", "clk_buf", "wordline_en",
                    "sense_en_bar", "sense_en"]
        else:
            return ["precharge_en_bar", "write_en_bar", "write_en", "clk_bar", "clk_buf", "wordline_en",
                    "sense_en", "tri_en", "tri_en_bar", "sample_en_bar"]

    def calculate_rail_offsets(self):
        self.control_names = self.get_control_names()

        num_horizontal_rails = len(self.control_names)
        self.control_rail_pitch = self.m3_width + self.line_end_space

        self.logic_buffers_bottom = 0

        self.trigate_y = 0.5*self.rail_height + (self.logic_buffers_bottom +
                                                 (1+num_horizontal_rails)*self.control_rail_pitch +
                                                 self.control_buffers.height)

        self.mid_gnd_offset = - 2*self.wide_m1_space - self.vdd_rail_width
        self.mid_vdd_offset = self.mid_gnd_offset - self.wide_m1_space - self.vdd_rail_width

        fill_height = m2m3.second_layer_height + self.m2_width
        (self.fill_height, self.fill_width) = self.calculate_min_m1_area(fill_height, self.m2_width)

    def connect_control_buffers(self):
        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"
        if self.mirror_sense_amp:
            connections = ["bank_sel", "read_buf", "clk", "clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                           "write_en", "write_en_bar",
                           "sense_en", "sense_en_bar", vdd_name, "gnd"]
            if OPTS.sense_trigger_delay > 0:
                connections.append("sense_trig")
            self.connect_inst(connections)
        else:
            if OPTS.baseline:

                extra_pins = ["tri_en", "tri_en_bar"]
            else:
                extra_pins = ["sense_precharge_bar"]
            self.connect_inst(["bank_sel", "read_buf", "clk", "sense_trig", "clk_buf", "clk_bar", "wordline_en",
                               "precharge_en_bar", "write_en", "write_en_bar",
                               "sense_en"] + extra_pins + ["sample_en_bar", vdd_name, "gnd"])

    def add_control_buffers(self):
        offset = vector(self.control_buffers.width, self.logic_buffers_bottom)
        self.control_buffers_inst = self.add_inst("control_buffers", mod=self.control_buffers,
                                                  offset=offset, mirror="MY")
        self.connect_control_buffers()

    def add_operation_flop(self, offset):
        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"
        self.read_buf_inst = self.add_inst("read_buf", mod=self.control_flop, offset=offset, mirror="MY")
        self.connect_inst(["read", "clk", "read_buf", vdd_name, "gnd"])

        self.copy_layout_pin(self.read_buf_inst, "din", "read")

    def add_read_flop(self):

        x_offset = self.control_buffers_inst.rx() + self.poly_pitch + self.control_flop.width
        offset = vector(x_offset, self.logic_buffers_bottom + self.control_buffers.height - self.control_flop.height)
        self.add_operation_flop(offset)

        # fill implants between read_buf and logic_buffers
        flop_inverter = self.control_flop.buffer.buffer_invs[-1]
        control_instances = self.control_buffers.insts
        first_control_instance = min(control_instances, key=lambda x: x.lx())

        if isinstance(first_control_instance.mod, pgate):
            control_mod = first_control_instance.mod
            control_mod_offset = 0
        elif isinstance(first_control_instance.mod, BufferStage):
            control_mod = first_control_instance.mod.module_insts[0].mod
            control_mod_offset = first_control_instance.mod.module_insts[0].offset.x
        else:
            control_mod = first_control_instance.mod.logic_inst.mod
            control_mod_offset = first_control_instance.mod.logic_inst.offset.x

        flop_y_offset = self.read_buf_inst.by() + self.control_flop.buffer_inst.by()
        flop_x_offset = (self.read_buf_inst.rx() - self.control_flop.buffer_inst.lx()
                         - self.control_flop.buffer.module_insts[-1].lx())

        control_y_offset = self.control_buffers_inst.by() + first_control_instance.by()
        control_x_offset = (self.control_buffers_inst.rx() - first_control_instance.lx() - control_mod_offset)

        for layer in ["pimplant", "nimplant"]:
            flop_rect = self.rightmost_largest_rect(flop_inverter.get_layer_shapes(layer))
            control_rect = self.rightmost_largest_rect(control_mod.get_layer_shapes(layer))

            bottom = max(flop_rect.by() + flop_y_offset, control_rect.by() + control_y_offset)
            top = min(flop_rect.uy() + flop_y_offset, control_rect.uy() + control_y_offset)

            left = control_x_offset - control_rect.lx()
            right = flop_x_offset - flop_rect.rx()
            self.add_rect(layer, offset=vector(left, bottom), width=right - left, height=top - bottom)

    def add_tri_gate_array(self):
        """ data tri gate to drive the data bus """

        y_offset = self.trigate_y

        self.tri_gate_array_inst = self.add_inst(name="tri_gate_array", mod=self.tri_gate_array,
                                                 offset=vector(0, y_offset))
        temp = []
        for i in range(self.word_size):
            temp.append("and_out[{0}]".format(i))
        for i in range(self.word_size):
            temp.append("DATA[{0}]".format(i))
        temp.extend(["tri_en", "tri_en_bar", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_data_mask_flops(self):
        data_connections = []
        mask_connections = []
        vdd_name = "vdd_data_flops" if OPTS.separate_vdd else "vdd"
        for i in range(self.word_size):
            data_connections.append("DATA[{}]".format(i))
            mask_connections.append("MASK[{}]".format(i))
        for i in range(self.word_size):
            data_connections.extend("data_in[{0}] data_in_bar[{0}]".format(i).split())
            mask_connections.extend("mask_in[{0}] mask_in_bar[{0}]".format(i).split())
        data_connections.extend([self.get_data_clk(), vdd_name, "gnd"])
        mask_connections.extend([self.get_mask_clk(), vdd_name, "gnd"])

        y_offset = self.get_mask_flops_y_offset()

        self.mask_in_flops_inst = self.add_inst("mask_in", mod=self.msf_mask_in, offset=vector(0, y_offset))
        self.connect_inst(mask_connections)

        y_offset = self.get_data_flops_y_offset()

        self.data_in_flops_inst = self.add_inst("data_in", mod=self.msf_data_in, offset=vector(0, y_offset))
        self.connect_inst(data_connections)

    def get_mask_clk(self): return "clk_buf"

    def get_data_clk(self): return "clk_bar"

    def get_mask_flops_y_offset(self):
        return self.tri_gate_array_inst.uy()

    def get_data_flops_y_offset(self):
        gnd_pins = self.msf_mask_in.get_pins("gnd")
        top_mask_gnd_pin = max(gnd_pins, key=lambda x: x.uy())

        bottom_data_gnd_pin = min(self.msf_data_in.get_pins("gnd"), key=lambda x: x.uy())

        implant_space = drc["parallel_implant_to_implant"]

        return self.mask_in_flops_inst.by() + implant_space + top_mask_gnd_pin.uy() - bottom_data_gnd_pin.by()

    def get_write_driver_offset(self):
        return self.data_in_flops_inst.ul()

    def add_write_driver_array(self):
        """Temp write driver, replace with mask support"""

        self.write_driver_array_inst = self.add_inst(name="write_driver_array",
                                                     mod=self.write_driver_array,
                                                     offset=self.get_write_driver_offset())

        temp = []
        for i in range(self.word_size):
            temp.append("data_in[{0}]".format(i))
            temp.append("data_in_bar[{0}]".format(i))

        if self.words_per_row > 1:
            suffix = "_out"
        else:
            suffix = ""
        for i in range(self.word_size):
            temp.append("bl{0}[{1}]".format(suffix, i))
            temp.append("br{0}[{1}]".format(suffix, i))
        for i in range(self.word_size):
            temp.append("mask_in_bar[{0}]".format(i))

        temp.extend(["write_en", "write_en_bar", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_sense_amp_array(self):
        self.sense_amp_array_offset = self.write_driver_array_inst.ul()
        self.sense_amp_array_inst = self.add_inst(name="sense_amp_array", mod=self.sense_amp_array,
                                                  offset=self.sense_amp_array_offset)
        temp = []
        if self.words_per_row > 1:
            suffix = "_out"
        else:
            suffix = ""
        for i in range(self.word_size):
            temp.append("bl{0}[{1}]".format(suffix, i))
            temp.append("br{0}[{1}]".format(suffix, i))

            temp.append("and_out[{0}]".format(i))

        if self.mirror_sense_amp:
            temp.extend(["sense_en", "sense_en_bar", "vdd", "gnd"])
        else:
            temp.extend(["sense_en", "precharge_en_bar", "sample_en_bar", "vdd", "gnd"])
        self.connect_inst(temp)

    def get_precharge_y(self):
        return self.sense_amp_array_inst.uy() + self.precharge_array.height

    def add_precharge_array(self):
        """ Adding Precharge """
        y_offset = self.get_precharge_y()
        self.precharge_array_inst=self.add_inst(name="precharge_array",
                                                mod=self.precharge_array,
                                                mirror="MX",
                                                offset=vector(0, y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        temp.extend(["precharge_en_bar", "vdd"])
        self.connect_inst(temp)

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        # TODO fix space hack
        y_offset = self.precharge_array_inst.uy() + self.wide_m1_space + 0.105
        self.bitcell_array_inst=self.add_inst(name="bitcell_array",
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

    def add_wordline_driver(self):
        """ Wordline Driver """

        # The wordline driver is placed to the right of one of the decoders .

        # TODO nwell space hack

        x_offset = self.mid_vdd_offset - (self.wordline_driver.width + self.wide_m1_space + 0.03)

        self.wordline_driver_inst=self.add_inst(name="wordline_driver", mod=self.wordline_driver,
                                                offset=vector(x_offset, self.bitcell_array_inst.by()))

        temp = []
        for i in range(self.num_rows):
            temp.append(self.get_wordline_in_net().format(i))
        for i in range(self.num_rows):
            temp.append("wl[{0}]".format(i))
        temp.append("wordline_en")
        vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"
        temp.append(vdd_name)
        temp.append("gnd")
        self.connect_inst(temp)

    def add_row_decoder(self):
        """  Add the hierarchical row decoder  """

        enable_rail_space = len(self.get_enable_names()) * self.control_rail_pitch

        x_offset = min((self.wordline_driver_inst.lx() - self.decoder.row_decoder_width),
                       self.leftmost_rail.lx() - self.m2_pitch - self.decoder.width - enable_rail_space)
        offset = vector(x_offset,  self.bitcell_array_inst.by()-self.decoder.predecoder_height)

        self.row_decoder_inst = self.add_inst(name="right_row_decoder", mod=self.decoder, offset=offset)

        temp = []
        for i in range(self.row_addr_size):
            temp.append("ADDR[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out[{0}]".format(j))
        vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"
        temp.extend([self.get_decoder_clk(), vdd_name, "gnd"])
        self.connect_inst(temp)

        self.min_point = min(self.control_buffers_inst.by(), self.row_decoder_inst.by())
        self.top = self.bitcell_array_inst.uy()

    def get_decoder_clk(self): return "clk_buf"

    def get_control_rails_destinations(self):
        if self.mirror_sense_amp:
            destination_pins = {
                "sense_en": self.tri_gate_array_inst.get_pins("en") + self.sense_amp_array_inst.get_pins("en"),
                "sense_en_bar": self.tri_gate_array_inst.get_pins("en_bar") +
                                self.sense_amp_array_inst.get_pins("en_bar"),
                "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
                "clk_buf": self.mask_in_flops_inst.get_pins("clk"),
                "clk_bar": self.data_in_flops_inst.get_pins("clk"),
                "write_en": self.write_driver_array_inst.get_pins("en"),
                "write_en_bar": self.write_driver_array_inst.get_pins("en_bar"),
                "wordline_en": self.precharge_array_inst.get_pins("en"),
            }
        else:
            destination_pins = {
                "sense_en": self.sense_amp_array_inst.get_pins("en"),
                "tri_en": self.tri_gate_array_inst.get_pins("en"),
                "tri_en_bar": self.tri_gate_array_inst.get_pins("en_bar"),
                "sample_en_bar": self.sense_amp_array_inst.get_pins("sampleb"),
                "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
                "clk_buf": self.mask_in_flops_inst.get_pins("clk"),
                "clk_bar": self.data_in_flops_inst.get_pins("clk"),
                "write_en": self.write_driver_array_inst.get_pins("en"),
                "write_en_bar": self.write_driver_array_inst.get_pins("en_bar"),
                "wordline_en": self.precharge_array_inst.get_pins("en"),
            }
            if OPTS.baseline:
                destination_pins["precharge_en_bar"] += \
                    self.sense_amp_array_inst.get_pins("preb")
        return destination_pins

    def add_control_rails(self):

        destination_pins = self.get_control_rails_destinations()

        y_offset = self.control_buffers_inst.get_pin("clk_buf").uy() + 0.5*self.rail_height + self.m2_space
        x_offset = (self.mid_vdd_offset - (len(self.control_names)*self.control_rail_pitch)
                    - (self.wide_m1_space-self.line_end_space))

        rail_names = list(sorted(destination_pins.keys(),
                                 key=lambda x: self.control_buffers_inst.get_pin(x).lx()))
        self.rail_names = rail_names

        for i in range(len(rail_names)):
            rail_name = rail_names[i]
            control_pin = self.control_buffers_inst.get_pin(rail_name)
            self.add_rect("metal2", offset=control_pin.ul(), height=y_offset-control_pin.uy())
            self.add_rect("metal3", offset=vector(x_offset, y_offset), width=control_pin.rx()-x_offset)

            self.add_contact_center(m2m3.layer_stack, offset=vector(control_pin.cx(),
                                                                    y_offset+0.5*self.m2_width), rotate=90)

            dest_pins = destination_pins[rail_name]

            if not dest_pins:
                rail = self.add_rect("metal3", offset=vector(x_offset, y_offset), height=m2m3.height)
            else:
                self.add_contact(m2m3.layer_stack, offset=vector(x_offset, y_offset))
                top_pin = max(dest_pins, key=lambda x: x.uy())
                rail = self.add_rect("metal2", offset=vector(x_offset, y_offset), height=top_pin.uy()-y_offset)
            setattr(self, rail_name+"_rail", rail)

            if not rail_name == "wordline_en":
                for dest_pin in dest_pins:
                    if dest_pin.layer == "metal2":
                        self.add_contact(m2m3.layer_stack, offset=dest_pin.ll(), rotate=90)
                        self.add_rect("metal3", offset=vector(rail.lx(), dest_pin.by()),
                                      width=dest_pin.lx()-rail.lx())
                        self.add_contact(m2m3.layer_stack,
                                         offset=vector(rail.lx(), dest_pin.cy()-0.5*m2m3.second_layer_height))
                    else:
                        if dest_pin.layer == "metal3":
                            via = m2m3
                        elif dest_pin.layer == "metal1":
                            via = m1m2
                        else:
                            debug.error("Invalid layer", 1)
                        self.add_rect(dest_pin.layer, offset=vector(rail.lx(), dest_pin.by()),
                                      width=dest_pin.lx() - rail.lx())
                        if rail_name == "write_en" and (self.control_buffers_inst.get_pin("write_en").lx() >
                            self.control_buffers_inst.get_pin("write_en_bar").lx()):
                            self.add_contact(via.layer_stack, offset=vector(rail.lx(), dest_pin.by()))
                        else:
                            self.add_contact(via.layer_stack,
                                             offset=vector(rail.lx(), dest_pin.uy()-via.second_layer_height))

            y_offset += self.control_rail_pitch
            x_offset += self.control_rail_pitch

        self.leftmost_rail = getattr(self, rail_names[0]+"_rail")

    def get_right_vdd_offset(self):
        return max(self.control_buffers_inst.rx(), self.bitcell_array_inst.rx(),
                   self.read_buf_inst.rx()) + self.wide_m1_space

    def add_vdd_gnd_rails(self):
        self.height = self.top - self.min_point

        right_vdd_offset = self.get_right_vdd_offset()
        right_gnd_offset = right_vdd_offset + self.vdd_rail_width + self.wide_m1_space
        left_vdd_offset = self.row_decoder_inst.lx() - self.wide_m1_space - self.vdd_rail_width
        left_gnd_offset = left_vdd_offset - self.wide_m1_space - self.vdd_rail_width

        offsets = [self.mid_gnd_offset, right_gnd_offset, self.mid_vdd_offset, right_vdd_offset,
                   left_vdd_offset, left_gnd_offset]
        left_vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"
        pin_names = ["gnd", "gnd", "vdd", "vdd", left_vdd_name, "gnd"]
        pin_layers = self.get_vdd_gnd_rail_layers()
        attribute_names = ["mid_gnd", "right_gnd", "mid_vdd", "right_vdd", "left_vdd", "left_gnd"]
        for i in range(6):
            pin = self.add_layout_pin(pin_names[i], pin_layers[i],
                                      vector(offsets[i], self.min_point), height=self.height,
                                      width=self.vdd_rail_width)
            setattr(self, attribute_names[i], pin)
        # for IDE assistance
        self.mid_gnd = getattr(self, "mid_gnd")
        self.right_gnd = getattr(self, "right_gnd")
        self.mid_vdd = getattr(self, "mid_vdd")
        self.right_vdd = getattr(self, "right_vdd")
        self.left_vdd = getattr(self, "left_vdd")
        self.left_gnd = getattr(self, "left_gnd")

    def get_sense_amp_dout(self):
        return "data"

    def get_vdd_gnd_rail_layers(self):
        return ["metal2", "metal1", "metal2", "metal2", "metal2", "metal1"]

    def get_collisions(self):
        return [
            (self.control_buffers_inst.by(), self.tri_gate_array_inst.by()),

            (self.tri_gate_array_inst.get_pin("en").uy(),
             self.tri_gate_array_inst.get_pin("en_bar").uy()),

            (self.sense_amp_array_inst.by() - m3m4.second_layer_height - self.wide_m1_space,
             self.sense_amp_array_inst.uy()),
        ]

    def route_bitcell(self):
        for row in range(self.num_rows):
            wl_in = self.bitcell_array_inst.get_pin("wl[{}]".format(row))
            driver_out = self.wordline_driver_inst.get_pin("wl[{0}]".format(row))
            self.add_rect("metal1", offset=vector(driver_out.rx(), wl_in.by()),
                          width=wl_in.lx()-driver_out.rx(), height=wl_in.height())

        for pin in self.bitcell_array_inst.get_pins("vdd"):
            self.route_vdd_pin(pin)

        for pin in self.bitcell_array_inst.get_pins("gnd"):
            self.route_gnd_pin(pin)

    def route_precharge(self):
        pin_names = ["bl", "br"]
        for col in range(self.num_cols):
            for pin_name in pin_names:
                precharge_pin = self.precharge_array_inst.get_pin(pin_name + "[{}]".format(col))
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name + "[{}]".format(col))

                self.add_rect(precharge_pin.layer, offset=precharge_pin.ul(),
                              height=bitcell_pin.by()-precharge_pin.uy())

        self.route_vdd_pin(self.precharge_array_inst.get_pin("vdd"), via_rotate=0)

    def route_sense_amp_common(self):

        for col in range(self.num_cols):
            # route bitlines
            for pin_name in ["bl", "br"]:
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name+"[{}]".format(col))
                sense_pin = self.sense_amp_array_inst.get_pin(pin_name+"[{}]".format(col))
                precharge_pin = self.precharge_array_inst.get_pin(pin_name+"[{}]".format(col))

                self.add_rect("metal4", offset=sense_pin.ul(), height=precharge_pin.uy()-sense_pin.uy())
                offset = precharge_pin.ul() - vector(0, m2m3.second_layer_height)
                self.add_contact(m2m3.layer_stack, offset=offset)
                self.add_contact(m3m4.layer_stack, offset=offset)
                via_extension = drc["min_wide_metal_via_extension"]
                if pin_name == "bl":
                    x_offset = bitcell_pin.lx() - via_extension
                else:
                    x_offset = bitcell_pin.rx() - self.fill_width + via_extension
                self.add_rect("metal3", offset=vector(x_offset, precharge_pin.uy()-self.fill_height),
                              width=self.fill_width, height=self.fill_height)
                self.add_rect("metal2", offset=precharge_pin.ul(), height=bitcell_pin.by()-precharge_pin.uy())
        # route ground
        if self.mirror_sense_amp:
            for pin in self.sense_amp_array_inst.get_pins("gnd"):
                self.route_gnd_pin(pin)

    def route_sense_amp(self):
        self.route_sense_amp_common()

        # route vdd

        if self.mirror_sense_amp:
            for pin in self.sense_amp_array_inst.get_pins("vdd"):
                self.route_vdd_pin(pin, via_rotate=0)
        else:
            vdd_pins = self.sense_amp_array_inst.get_pins("vdd")
            pin = max(vdd_pins, key=lambda x: x.uy())
            self.add_rect("metal1", offset=vector(self.mid_vdd.lx(), pin.by()),
                          width=self.right_vdd.rx() - self.mid_vdd.lx(), height=pin.height())

            self.add_contact(m1m2.layer_stack, offset=vector(self.right_vdd.lx() + 0.2, pin.by()),
                                    size=[2, 1], rotate=90)
            self.add_contact(m1m2.layer_stack, offset=vector(self.mid_vdd.lx() + 0.2, pin.by()),
                             size=[2, 1], rotate=90)

    def route_write_driver(self):
        for col in range(0, int(self.num_cols / self.words_per_row)):
            # connect bitline to sense amp
            for pin_name in ["bl", "br"]:
                driver_pin = self.write_driver_array_inst.get_pin(pin_name + "[{}]".format(col))
                self.add_contact(m3m4.layer_stack, offset=driver_pin.ul() - vector(0, m3m4.second_layer_height))

            # route data_bar
            flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(col))
            self.add_rect("metal2", offset=flop_pin.ul(), height=driver_pin.by() - flop_pin.uy())
            self.add_contact(m2m3.layer_stack, offset=driver_pin.ll() - vector(0, m2m3.second_layer_height))

            # route data
            flop_pin = self.data_in_flops_inst.get_pin("dout[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data[{}]".format(col))
            offset = vector(driver_pin.lx(), flop_pin.uy() - self.m2_width)
            self.add_rect("metal2", offset=offset, width=flop_pin.rx() - offset.x)
            self.add_contact(m2m3.layer_stack, offset=offset)
            self.add_rect("metal3", offset=offset, height=driver_pin.by() - offset.y)

            # route mask_bar
            flop_pin = self.mask_in_flops_inst.get_pin("dout_bar[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("mask_bar[{}]".format(col))

            self.add_contact(m2m3.layer_stack, offset=flop_pin.ul())
            x_offset = driver_pin.rx() + self.parallel_line_space

            data_in = self.data_in_flops_inst.get_pin("din[{}]".format(col))
            y_bend = data_in.by() + m2m3.height + self.line_end_space

            self.add_rect("metal3", offset=flop_pin.ul(), height=y_bend - flop_pin.uy())
            self.add_rect("metal3", offset=vector(x_offset, y_bend), width=flop_pin.rx()-x_offset)

            self.add_rect("metal3", offset=vector(x_offset, y_bend), height=driver_pin.by() - y_bend)
            self.add_rect("metal3", offset=driver_pin.ll(), width=x_offset + self.m3_width - driver_pin.lx())

        # route power, gnd

        for pin in self.write_driver_array_inst.get_pins("vdd"):
            self.route_vdd_pin(pin, via_rotate=0)
        gnd_pins = self.write_driver_array_inst.get_pins("gnd")
        top_gnd = max(gnd_pins, key=lambda x: x.by())  # bottom pin overlaps flop gnds
        self.route_gnd_pin(top_gnd, via_rotate=0)

    def route_flops(self):
        if OPTS.separate_vdd:
            self.copy_layout_pin(self.data_in_flops_inst, "vdd", "vdd_data_flops")
            self.copy_layout_pin(self.mask_in_flops_inst, "vdd", "vdd_data_flops")
        else:
            for pin in self.data_in_flops_inst.get_pins("vdd") + self.mask_in_flops_inst.get_pins("vdd"):
                self.route_vdd_pin(pin)
        for pin in self.mask_in_flops_inst.get_pins("gnd"):
            self.route_gnd_pin(pin, via_rotate=0)

        data_in_gnds = list(sorted(self.data_in_flops_inst.get_pins("gnd"), key=lambda x: x.by()))
        self.route_gnd_pin(data_in_gnds[0], via_rotate=0)
        self.route_gnd_pin(data_in_gnds[1], via_rotate=90)

        for col in range(self.num_cols):
            self.copy_layout_pin(self.mask_in_flops_inst, "din[{}]".format(col), "MASK[{}]".format(col))

    def route_tri_gate(self):
        self.route_vdd_pin(self.tri_gate_array_inst.get_pin("vdd"))
        self.route_gnd_pin(self.tri_gate_array_inst.get_pin("gnd"))

        mid_flop_y = 0.5 * (self.mask_in_flops_inst.by() + self.mask_in_flops_inst.uy())

        for col in range(self.num_cols):

            # route tri-gate output to data flop
            tri_gate_out = self.tri_gate_array_inst.get_pin("out[{}]".format(col))
            flop_in = self.data_in_flops_inst.get_pin("din[{}]".format(col))

            self.add_contact(m2m3.layer_stack, offset=flop_in.ll())

            # bypass mask din overlap

            x_offset = tri_gate_out.rx() + self.wide_m1_space
            self.add_rect("metal3", offset=vector(flop_in.lx(), mid_flop_y), height=flop_in.by() - mid_flop_y)
            self.add_rect("metal3", offset=vector(flop_in.lx(), mid_flop_y),
                          width=x_offset + self.m3_width - flop_in.lx())

            y_offset = tri_gate_out.uy() - self.m3_width

            self.add_rect("metal3", offset=vector(x_offset, y_offset), height=mid_flop_y - y_offset)
            self.add_rect("metal3", offset=vector(tri_gate_out.lx(), y_offset), width=x_offset - tri_gate_out.lx())
            self.add_contact(m2m3.layer_stack, offset=tri_gate_out.ul() - vector(0, m2m3.second_layer_height))

            self.copy_layout_pin(self.tri_gate_array_inst, "out[{}]".format(col), "DATA[{}]".format(col))

            # route sense amp output to tri-gate input
            sense_pin = self.sense_amp_array_inst.get_pin(self.get_sense_amp_dout()+"[{}]".format(col))
            tri_gate_in = self.tri_gate_array_inst.get_pin("in[{}]".format(col))
            self.add_rect("metal4", offset=vector(tri_gate_in.lx(), sense_pin.by()),
                          width=sense_pin.rx()-tri_gate_in.lx())
            self.add_rect("metal4", offset=tri_gate_in.ul(), height=sense_pin.by()-tri_gate_in.uy()+self.m4_width)
            self.add_contact(m2m3.layer_stack, offset=tri_gate_in.ul()-vector(0, m2m3.second_layer_height))
            self.add_contact(m3m4.layer_stack, offset=tri_gate_in.ul()-vector(0, m3m4.second_layer_height))
            self.add_rect("metal3", offset=vector(tri_gate_in.rx()-self.fill_width, tri_gate_in.uy()-self.fill_height),
                          width=self.fill_width, height=self.fill_height)

    def route_read_buf(self):
        # route clk in from control_buffers clk in
        flop_clk_pin = self.read_buf_inst.get_pin("clk")
        control_clk_pin = self.control_buffers_inst.get_pin("clk")
        read_pin = self.read_buf_inst.get_pin("din")

        x_offset = max(flop_clk_pin.rx() + m1m2.second_layer_height - self.m2_width,
                       read_pin.rx() + self.line_end_space)

        self.add_rect("metal3", offset=control_clk_pin.lr(), width=x_offset - control_clk_pin.rx())
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset, control_clk_pin.by()))

        self.add_rect("metal2", offset=vector(x_offset, control_clk_pin.by()),
                      height=flop_clk_pin.uy() - control_clk_pin.by())
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset + self.m2_width, flop_clk_pin.by()),
                         rotate=90)
        self.add_rect("metal1", offset=flop_clk_pin.lr(), width=x_offset-flop_clk_pin.rx())

        # read output to control buffers read
        read_out = self.read_buf_inst.get_pin("dout")
        read_in = self.control_buffers_inst.get_pin("read")
        offset = read_in.lr()
        self.add_rect("metal3", offset=offset, width=read_out.lx() - offset.x)
        self.add_contact(m2m3.layer_stack, offset=vector(read_out.rx(), offset.y), rotate=90)
        self.add_rect("metal2", offset=vector(read_out.lx(), offset.y), height=read_out.by()-offset.y)

    def route_control_buffer(self):
        self.copy_layout_pin(self.control_buffers_inst, "bank_sel", "bank_sel")
        self.copy_layout_pin(self.control_buffers_inst, "clk", "clk")
        self.copy_sense_trig_pin()

        # vdd
        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"

        if OPTS.separate_vdd:
            self.copy_layout_pin(self.control_buffers_inst, "vdd", vdd_name)
        else:
            self.route_vdd_pin(self.control_buffers_inst.get_pin("vdd"))

        # gnd
        read_flop_gnd = self.read_buf_inst.get_pin("gnd")
        control_buffers_gnd = self.control_buffers_inst.get_pin("gnd")

        # join grounds
        # control_buffers gnd to read gnd
        offset = vector(control_buffers_gnd.rx() - read_flop_gnd.height(), read_flop_gnd.by())
        self.add_rect("metal1", offset=offset, width=read_flop_gnd.lx() - offset.x, height=read_flop_gnd.height())
        self.add_rect("metal1", offset=offset, width=read_flop_gnd.height(),
                      height=control_buffers_gnd.by() - read_flop_gnd.by())

        # control_buffers to rail
        self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), control_buffers_gnd.by()),
                      width=control_buffers_gnd.lx() - self.mid_gnd.lx(), height=control_buffers_gnd.height())
        self.add_power_via(control_buffers_gnd, self.mid_gnd, via_rotate=90)

        # read flop gnd to rail
        self.add_rect("metal1", offset=read_flop_gnd.lr(), height=read_flop_gnd.height(),
                      width=self.right_gnd.rx() - read_flop_gnd.rx())

    def copy_sense_trig_pin(self):
        if not self.mirror_sense_amp or OPTS.sense_trigger_delay > 0:
            self.copy_layout_pin(self.control_buffers_inst, "sense_trig", "sense_trig")

    def route_wordline_driver(self):
        # route enable signal
        en_pin = self.wordline_driver_inst.get_pin("en")
        en_rail = self.wordline_en_rail
        y_offset = self.wordline_driver_inst.by()

        self.add_rect("metal2", offset=en_rail.ul(), height=y_offset - en_rail.uy())
        self.add_rect("metal2", offset=vector(en_pin.lx(), y_offset), width=en_rail.rx() - en_pin.lx())

        if OPTS.separate_vdd:
            self.copy_layout_pin(self.wordline_driver_inst, "vdd", "vdd_wordline")

        if OPTS.separate_vdd:
            pin_end = [self.bitcell_array_inst.lx(), self.wordline_driver_inst.rx()]
        else:
            pin_end = [self.bitcell_array_inst.lx(), self.bitcell_array_inst.rx()]

        pin_names = ["gnd", "vdd"]
        for i in range(2):
            pin_name = pin_names[i]
            for pin in self.wordline_driver_inst.get_pins(pin_name):
                self.add_rect(pin.layer, offset=vector(self.row_decoder_inst.rx(), pin.by()),
                              height=pin.height(),
                              width=pin_end[i]-self.row_decoder_inst.rx())

    def route_decoder(self):
        self.route_right_decoder_power()
        self.join_right_decoder_nwell()
        # route clk
        clk_rail = self.clk_buf_rail
        clk_pins = self.row_decoder_inst.get_pins("clk")
        # find closest
        target_y = clk_rail.by()+m2m3.second_layer_height
        clk_pin = min(clk_pins, key=lambda x: min(abs(target_y - x.by() + m2m3.height),
                                                  abs(target_y - x.uy() - m2m3.height)))

        self.add_rect("metal3", offset=vector(clk_pin.lx(), target_y), width=clk_rail.rx() - clk_pin.lx())

        if target_y < clk_pin.by():
            self.add_rect("metal2", offset=vector(clk_pin.lx(), target_y), height=clk_pin.by()-target_y)

        # find closest vdd-gnd pin to add via, otherwise via in between cell may clash with decoder address pin via
        y_offset = clk_rail.by() + m2m3.second_layer_height
        vdd_gnd = self.row_decoder_inst.get_pins("vdd") + self.row_decoder_inst.get_pins("gnd")
        valid_vdd_gnd = filter(lambda x: x.by() > y_offset + self.line_end_space, vdd_gnd)
        closest_vdd_gnd = min(valid_vdd_gnd, key=lambda x: x.by() - y_offset)

        self.add_contact(m2m3.layer_stack, offset=vector(clk_pin.lx(), closest_vdd_gnd.by()))
        self.add_rect("metal3", offset=vector(clk_pin.lx(), target_y),
                      height=closest_vdd_gnd.by() - target_y)

        if closest_vdd_gnd.cy() - 0.5*m2m3.height > clk_pin.uy():
            self.add_rect("metal2", offset=clk_pin.ul(), height=closest_vdd_gnd.cy()-clk_pin.uy())

        # copy address ports
        for i in range(self.addr_size):
            self.copy_layout_pin(self.row_decoder_inst, "A[{}]".format(i), "ADDR[{}]".format(i))

    def route_right_decoder_power(self):
        for pin in self.row_decoder_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=vector(self.left_gnd.lx(), pin.by()),
                          width=pin.lx() - self.left_gnd.lx(), height=pin.height())
            if self.left_gnd.layer == "metal2":
                self.add_power_via(pin, self.left_gnd)

        for pin in self.row_decoder_inst.get_pins("vdd"):  # ensure decoder vdd is connected to wordline driver's
            if pin.uy() > self.wordline_driver_inst.by():
                pin_right = self.wordline_driver_inst.lx()
            else:
                pin_right = pin.lx()
            self.add_rect("metal1", offset=vector(self.left_vdd.lx(), pin.by()),
                          width=pin_right - self.left_vdd.lx(), height=pin.height())
            self.add_power_via(pin, self.left_vdd)

    def join_right_decoder_nwell(self):

        layers = ["nwell", "pimplant"]
        purposes = ["drawing", "drawing"]

        decoder_inverter = self.decoder.inv_inst[-1].mod
        driver_nand = self.wordline_driver.logic_buffer.logic_mod

        row_decoder_right = self.row_decoder_inst.lx() + self.decoder.row_decoder_width
        x_shift = self.wordline_driver.buffer_insts[-1].lx()

        for i in range(2):
            decoder_rect = max(decoder_inverter.get_layer_shapes(layers[i], purposes[i]),
                               key=lambda x: x.height)
            logic_rect = max(driver_nand.get_layer_shapes(layers[i], purposes[i]),
                             key=lambda x: x.height)
            top_most = max([decoder_rect, logic_rect], key=lambda x: x.by())
            fill_height = driver_nand.height - top_most.by()
            # extension of rect past top of cell
            rect_y_extension = top_most.uy() - driver_nand.height
            fill_width = self.wordline_driver_inst.lx() - row_decoder_right + x_shift

            for vdd_pin in self.row_decoder_inst.get_pins("vdd"):
                if utils.round_to_grid(vdd_pin.cy()) == utils.round_to_grid(
                        self.wordline_driver_inst.by()):  # first row
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - rect_y_extension),
                                  width=fill_width, height=top_most.height)
                elif vdd_pin.cy() > self.wordline_driver_inst.by():  # row decoder
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - fill_height),
                                  width=fill_width, height=2 * fill_height)

    def route_wordline_in(self):
        # route decoder in
        for row in range(self.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            wl_in = self.wordline_driver_inst.get_pin("in[{}]".format(row))

            self.add_contact(m2m3.layer_stack, offset=vector(decoder_out.ul() - vector(0, m2m3.second_layer_height)))
            x_offset = wl_in.cx() + 0.5 * self.m3_width
            self.add_rect("metal3", offset=decoder_out.ul(), width=x_offset - decoder_out.lx())
            self.add_rect("metal3", offset=vector(x_offset - self.m3_width, wl_in.cy()),
                          height=decoder_out.uy() - wl_in.cy())
            self.add_contact_center(m2m3.layer_stack, wl_in.center())
            self.add_contact_center(m1m2.layer_stack, wl_in.center())

            self.add_rect_center("metal2", offset=wl_in.center(), width=self.fill_width, height=self.fill_height)

    def add_power_vias(self):
        for i in range(len(self.power_grid_vias)):
            if i % 2 == 0:  # vdd
                via_x = [self.left_vdd.lx(), self.mid_vdd.lx(),
                         self.right_vdd.lx()]
                mirrors = ["R0", "R0", "MY"]
                via_mods = [self.m2mtop, self.m2mtop, self.m2mtop]
                for j in range(3):
                    self.add_inst(via_mods[j].name, via_mods[j],
                                  offset=vector(via_x[j]+ 0.5 * self.vdd_rail_width, self.power_grid_vias[i]),
                                  mirror=mirrors[j])
                    self.connect_inst([])
                if OPTS.separate_vdd:
                    start_x = via_x[1]
                    self.add_rect(self.bottom_power_layer, offset=vector(via_x[0], self.power_grid_vias[i]),
                                  height=self.grid_rail_height, width=self.vertical_power_rail_offsets[1] - via_x[0])
                else:
                    start_x = via_x[0]
                self.vdd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(start_x, self.power_grid_vias[i]),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - start_x))
            else:  # gnd
                via_x = [self.left_gnd.lx(), self.mid_gnd.lx()+0.5*self.vdd_rail_width,
                         self.right_gnd.rx()]
                mirrors = ["R0", "R0", "MY"]
                via_mods = [self.m1mtop, self.m2mtop, self.m1mtop]
                for j in range(3):
                    self.add_inst(via_mods[j].name, via_mods[j],
                                  offset=vector(via_x[j], self.power_grid_vias[i]),
                                  mirror=mirrors[j])
                    self.connect_inst([])
                self.gnd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(self.left_gnd.lx(), self.power_grid_vias[i]),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - self.left_gnd.lx()))

    def route_gnd_pin(self, pin, add_via=True, via_rotate=90):
        self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), pin.by()),
                      width=self.right_gnd.rx()-self.mid_gnd.lx(), height=pin.height())
        if add_via:
            self.add_power_via(pin, self.mid_gnd, via_rotate)

    def route_vdd_pin(self, pin, add_via=True, via_rotate=90):
        self.add_rect("metal1", offset=vector(self.mid_vdd.lx(), pin.by()),
                      width=self.right_vdd.rx() - self.mid_vdd.lx(), height=pin.height())
        if add_via:
            self.add_power_via(pin, self.mid_vdd, via_rotate=via_rotate)
            self.add_power_via(pin, self.right_vdd, via_rotate=via_rotate)

    def add_power_via(self, pin, power_pin, via_rotate=90):
        self.add_contact_center(m1m2.layer_stack, offset=vector(power_pin.cx(), pin.cy()),
                                size=[2, 1], rotate=via_rotate)

    def add_decoder_power_vias(self):
        self.vdd_grid_rects = []
        self.gnd_grid_rects = []

        # for leftmost rails, power vias might clash with decoder metal3's
        m4m10 = ContactFullStack(start_layer=3, stop_layer=-1, centralize=False)
        max_left_power_y = self.wordline_driver_inst.by() - 3 * self.control_rail_pitch - self.m2mtop.second_layer_height
        for i in range(len(self.power_grid_vias)):
            via_y_offset = self.power_grid_vias[i]
            if i % 2 == 0:  # vdd
                # add vias to top
                via_x = [self.left_vdd.lx(), self.mid_vdd.lx()]
                for j in range(2):
                    if j == 0 and via_y_offset > max_left_power_y:
                        self.add_inst(m4m10.name, m4m10, offset=vector(self.left_vdd.lx(), via_y_offset))
                        self.connect_inst([])
                    else:
                        self.add_inst(self.m2mtop.name, self.m2mtop,
                                      offset=vector(via_x[j] + 0.5 * self.vdd_rail_width, via_y_offset))
                        self.connect_inst([])
                # connect rails horizontally
                if OPTS.separate_vdd:
                    start_x = via_x[1]
                    self.add_rect(self.bottom_power_layer, offset=vector(via_x[0], via_y_offset),
                                  height=self.grid_rail_height, width=self.vertical_power_rail_offsets[1] - via_x[0])
                else:
                    start_x = via_x[0]
                self.vdd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(start_x, via_y_offset),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - start_x))
            else:  # gnd
                via_x = [self.left_gnd.lx()+0.5*self.vdd_rail_width, self.mid_gnd.lx()+0.5*self.vdd_rail_width]
                for j in range(2):
                    if j == 0 and via_y_offset > max_left_power_y:
                        self.add_inst(m4m10.name, m4m10, offset=vector(self.left_gnd.lx(), via_y_offset))
                        self.connect_inst([])
                    else:
                        self.add_inst(self.m2mtop.name, self.m2mtop,
                                      offset=vector(via_x[j], self.power_grid_vias[i]))
                        self.connect_inst([])
                self.gnd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(self.left_gnd.lx(), self.power_grid_vias[i]),
                                                         height=self.grid_rail_height,
                                                         width=self.right_gnd.rx() - self.left_gnd.lx()))
        # Add m4 rails along existing m2 rails
        for rail in [self.left_gnd, self.left_vdd]:
            self.add_rect("metal4", offset=vector(rail.lx(), self.min_point), width=rail.width(),
                          height=self.wordline_driver_inst.uy()-self.min_point)
        # add m2-m4 via
        for row in range(self.num_rows):
            y_offset = self.wordline_driver_inst.by() + (row + 0.5) * self.bitcell_array.cell.height
            for x_offset in [self.left_gnd.cx(), self.left_vdd.cx()]:
                self.add_via_center(m2m3.layer_stack, offset=vector(x_offset, y_offset), size=[2, 2])
                self.add_via_center(m3m4.layer_stack, offset=vector(x_offset, y_offset), size=[2, 2])
                if x_offset == self.left_gnd.cx() and row > 0:
                    self.add_via_center(m1m2.layer_stack, offset=vector(x_offset, y_offset), size=[2, 2])

        # add Mtop vdd/gnd rails within decoder
        wide_m10_space = drc["wide_metal10_to_metal10"]
        vdd_x = self.left_vdd.lx() + self.m2mtop.width + wide_m10_space
        gnd_x = vdd_x + self.grid_rail_width + wide_m10_space
        vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"

        self.add_layout_pin(vdd_name, layer=self.top_power_layer, offset=vector(vdd_x, self.min_point),
                            width=self.grid_rail_width, height=self.height)

        # avoid clash with middle vdd vias
        if gnd_x + self.grid_rail_width + wide_m10_space < self.mid_vdd.cx() - 0.5 * self.m2mtop.width:
            self.add_layout_pin("gnd", layer=self.top_power_layer, offset=vector(gnd_x, self.min_point),
                                width=self.grid_rail_width, height=self.height)

            for rect in self.gnd_grid_rects:
                self.add_inst(self.m9m10.name, mod=self.m9m10,
                              offset=vector(gnd_x, rect.by()))
                self.connect_inst([])

        for rect in self.vdd_grid_rects:
            self.add_inst(self.m9m10.name, mod=self.m9m10,
                          offset=vector(vdd_x, rect.by()))
            self.connect_inst([])

    def add_right_rails_vias(self):
        vdd_x = self.right_vdd.cx()
        gnd_x = self.right_gnd.rx()

        for rect in self.vdd_grid_rects:
            self.add_inst(self.m2mtop.name, mod=self.m2mtop,
                          offset=vector(vdd_x, rect.by()))
            self.connect_inst([])

        for rect in self.gnd_grid_rects:
            self.add_inst(self.m1mtop.name, mod=self.m1mtop,
                          offset=vector(gnd_x, rect.by()), mirror="MY")
            self.connect_inst([])

    def calculate_rail_vias(self):
        """Calculates positions of power grid rail to M1/M2 vias. Avoids internal metal3 control pins"""
        # need to avoid the metal3 control signals

        via_positions = []

        self.m1mtop = m1mtop = ContactFullStack.m1mtop()
        self.add_mod(m1mtop)
        self.m2mtop = m2mtop = ContactFullStack.m2mtop()
        self.add_mod(m2mtop)

        self.bottom_power_layer = power_grid_layers[0]
        self.top_power_layer = power_grid_layers[1]

        self.grid_rail_height = grid_rail_height = max(m1mtop.first_layer_height, m2mtop.first_layer_height)
        self.grid_rail_width = m1mtop.second_layer_width

        grid_space = drc["power_grid_space"]
        grid_pitch = grid_space + grid_rail_height
        via_space = self.wide_m1_space

        bank_top = self.min_point + self.height

        collisions = list(sorted(self.get_collisions() +
                                 [(self.min_point, self.min_point + 2*self.wide_m1_space),
                                  (bank_top - grid_pitch, bank_top)],
                                 key=lambda x: x[0]))

        # combine/collapse overlapping collisions
        while True:
            i = 0
            num_overlaps = 0
            num_iterations = len(collisions)
            new_collisions = []
            while i < num_iterations:

                collision = collisions[i]
                if i < num_iterations - 1:
                    next_collision = collisions[i + 1]
                    if next_collision[0] <= collision[1]:
                        collision = (collision[0], max(collision[1], next_collision[1]))
                        num_overlaps += 1
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1
                new_collisions.append(collision)
            collisions = new_collisions
            if num_overlaps == 0:
                break

        # calculate via positions
        prev_y = -1.0e100
        for i in range(len(collisions)-1):
            collision = collisions[i]
            current_y = max(collision[1] + self.wide_m1_space, prev_y + grid_pitch)
            next_collision = collisions[i+1][0]
            while True:
                via_top = current_y + grid_rail_height
                if via_top > bank_top or via_top + via_space > next_collision:
                    break
                via_positions.append(current_y)
                prev_y = current_y
                current_y += grid_pitch

        self.power_grid_vias = via_positions

    def calculate_body_tap_rails_vias(self):
        self.m4m9 = ContactFullStack(start_layer=3, stop_layer=-2, centralize=False)
        self.m5m9 = ContactFullStack(start_layer=4, stop_layer=-2, centralize=False)

        wide_m10_space = drc["wide_metal10_to_metal10"]

        self.bitcell_power_vias = []
        self.vertical_power_rails_pos = []

        m4_via_width = self.m4m9.first_layer_width

        rails = utils.get_libcell_pins(["vdd", "gnd"], OPTS.body_tap)
        vdd_rail = rails["vdd"][0]
        gnd_rail = rails["gnd"][0]

        collisions = list(sorted(self.bitcell_array.tap_offsets))

        for x_offset in collisions:
            real_x_offset = self.bitcell_array_inst.lx() + x_offset
            vdd_x_offset = real_x_offset + vdd_rail.rx() - m4_via_width
            gnd_x_offset = real_x_offset + gnd_rail.lx()

            self.bitcell_power_vias.append((vdd_x_offset, gnd_x_offset))

        max_x_offset = self.right_gnd.rx() - self.m1mtop.width - wide_m10_space

        grid_collisions = self.bitcell_power_vias + [(self.right_vdd.lx(), self.right_gnd.lx())]

        for i in range(len(grid_collisions) - 1):
            offsets = grid_collisions[i]
            next_offset = grid_collisions[i+1][0]
            current_offset = offsets[1] + self.m4m9.width + wide_m10_space
            while True:
                rail_right_x = current_offset + self.grid_rail_width
                if rail_right_x > max_x_offset or rail_right_x > next_offset - wide_m10_space:
                    break
                self.vertical_power_rails_pos.append(current_offset)
                current_offset += wide_m10_space + self.grid_rail_width

        # remove first via since it clashes with middle rails
        if self.bitcell_power_vias[-1][0] > max_x_offset - wide_m10_space - self.m4m9.width:
            self.bitcell_power_vias = self.bitcell_power_vias[1:-1]
        else:
            self.bitcell_power_vias = self.bitcell_power_vias[1:]

    def get_body_taps_bottom(self):
        return self.tri_gate_array_inst.by()

    def route_body_tap_supplies(self):
        # TODO fix top layer

        self.calculate_body_tap_rails_vias()

        rails = utils.get_libcell_pins(["vdd", "gnd"], OPTS.body_tap)
        vdd_rail = rails["vdd"][0]
        gnd_rail = rails["gnd"][0]

        for x_offset in self.bitcell_array.tap_offsets:

            # join bitcell body tap power/gnd to bottom module tap power/gnd
            rail_y = self.get_body_taps_bottom()

            rail_height = self.bitcell_array_inst.by() - rail_y

            vdd_rail_x = x_offset + vdd_rail.lx()
            self.add_rect(vdd_rail.layer, offset=vector(vdd_rail_x, rail_y), width=vdd_rail.width(),
                          height=rail_height)

            gnd_rail_x = x_offset + gnd_rail.lx()
            self.add_rect(gnd_rail.layer, offset=vector(gnd_rail_x, rail_y), width=gnd_rail.width(),
                          height=rail_height)

        def get_via(rect):
            if rect.by() < self.bitcell_array_inst.by():
                via_mod = self.m5m9
            else:
                via_mod = self.m4m9
            return via_mod

        dummy_contact = contact(layer_stack=("metal4", "via4", "metal5"), dimensions=[1, 5])

        def connect_m4(via_inst, is_vdd):
            if via_inst.mod == self.m5m9:
                if is_vdd:
                    x_offset = via_inst.lx() + 0.11
                else:
                    x_offset = via_inst.lx()
                self.add_contact(layers=dummy_contact.layer_stack, size=dummy_contact.dimensions,
                                 offset=vector(x_offset, via_inst.by()))

        for vdd_via_x, gnd_via_x in self.bitcell_power_vias:

            # add m4m9 via
            for rect in self.vdd_grid_rects:
                via = get_via(rect)

                via_inst = self.add_inst(via.name, mod=via, offset=vector(vdd_via_x, rect.by()))
                self.connect_inst([])
                connect_m4(via_inst, is_vdd=True)

            for rect in self.gnd_grid_rects:
                via = get_via(rect)
                via_inst = self.add_inst(via.name, mod=via, offset=vector(gnd_via_x, rect.by()))
                self.connect_inst([])
                connect_m4(via_inst, is_vdd=False)

        # add vertical rails across bitcell array
        for i in range(len(self.vertical_power_rails_pos)):
            x_offset = self.vertical_power_rails_pos[i]
            self.add_rect(self.top_power_layer, offset=vector(x_offset, self.min_point),
                          width=self.grid_rail_width, height=self.height)

            if i % 2 == 0:
                for rect in self.vdd_grid_rects:

                    self.add_inst(self.m9m10.name, mod=self.m9m10,
                                  offset=vector(x_offset, rect.by()))
                    self.connect_inst([])
            else:
                for rect in self.gnd_grid_rects:
                    self.add_inst(self.m9m10.name, mod=self.m9m10,
                                  offset=vector(x_offset, rect.by()))
                    self.connect_inst([])

    def route_control_buffers_power(self):
        obstructions = [(self.control_buffers_inst.lx() - self.wide_m1_space,
                         self.read_buf_inst.rx()+self.wide_m1_space)]
        if hasattr(self, "max_right_buffer_x"):
            obstructions.append((self.min_right_buffer_x - self.wide_m1_space,
                                 self.max_right_buffer_x + self.wide_m1_space))

        rails = utils.get_libcell_pins(["vdd", "gnd"], OPTS.body_tap)
        tap_width = self.bitcell_array.body_tap.width
        vdd_rail = rails["vdd"][0]
        gnd_rail = rails["gnd"][0]

        def filter_func(offset):
            for obstruction in obstructions:
                if obstruction[0] <= offset <= obstruction[1] or offset <= obstruction[0] <= offset + tap_width:
                    return False
            return True

        tap_offsets = [self.bitcell_array_inst.lx() + x for x in self.bitcell_array.tap_offsets]
        tap_offsets = list(filter(filter_func, tap_offsets))
        vdd_pin = self.control_buffers.get_pin("vdd")
        gnd_pin = self.control_buffers.get_pin("gnd")

        via_size = [2, 1]
        dummy_via = contact(m1m2.layer_stack, dimensions=via_size)
        fill_width = vdd_rail.width()
        min_area = drc["minarea_metal1_contact"]

        fill_height = max(utils.ceil(min_area / fill_width), dummy_via.width)

        for tap_offset in tap_offsets:
            for (pin, rail) in [(vdd_pin, vdd_rail), (gnd_pin, gnd_rail)]:
                x_offset = rail.lx() + tap_offset
                self.add_rect("metal4", offset=vector(x_offset, pin.by()),
                              height=self.data_in_flops_inst.by()-pin.by(), width=rail.width())
                if rail == vdd_rail:
                    y_offset = pin.uy() - fill_height
                else:
                    y_offset = pin.by()
                for via in [m1m2, m2m3, m3m4]:
                    self.add_contact(via.layer_stack,
                                     offset=vector(x_offset+0.5*(rail.width()+dummy_via.height),
                                                   y_offset), size=via_size, rotate=90)

    @staticmethod
    def rightmost_largest_rect(rects):
        """Biggest rect to the right of the cell"""
        right_x = max([x.rx() for x in rects])
        return max(filter(lambda x: x.rx() >= 0.75 * right_x, rects), key=lambda x: x.height)

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
