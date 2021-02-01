import debug
from base import utils
from base.contact import m1m2, m2m3, cross_m2m3, cross_m1m2, m3m4
from base.design import METAL1, METAL2, NWELL, METAL3, METAL4
from base.vector import vector
from globals import OPTS
from modules.flop_buffer import FlopBuffer
from modules.hierarchical_predecode2x4 import hierarchical_predecode2x4
from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8
from modules.shared_decoder.cmos_bank import CmosBank
from sram import sram


class CmosSram(sram):
    wide_space = None
    bank_insts = bank = row_decoder = None
    column_decoder = column_decoder_inst = col_decoder_connections = None
    row_decoder_inst = None

    def __init__(self, word_size, num_words, num_banks, name, words_per_row=None,
                 add_power_grid=True):
        """Words will be split across banks in case of two banks"""
        assert num_banks in [1, 2], "Only one or two banks supported"
        assert word_size % 2 == 0, "Word-size must be even"
        assert words_per_row in [1, 2, 4, 8], "Max 8 words per row supported"
        if num_banks == 2:
            word_size = int(word_size / 2)
        self.add_power_grid = add_power_grid
        super().__init__(word_size, num_words, num_banks, name, words_per_row)
        # restore word-size
        self.word_size = num_banks * self.word_size

    def create_layout(self):
        self.single_bank = self.num_banks == 1
        self.wide_space = self.get_wide_space(METAL1)
        self.create_modules()
        self.add_modules()

        self.min_point = min(self.row_decoder_inst.by(), self.bank_insts[0].by())

        self.route_layout()

    def create_modules(self):
        debug.info(1, "Create sram modules")
        self.create_bank()
        self.row_decoder = self.bank.decoder
        self.min_point = self.bank.min_point
        self.fill_width = self.bank.fill_width
        self.fill_height = self.bank.fill_height
        self.row_decoder_y = self.bank.bitcell_array_inst.uy() - self.row_decoder.height
        self.create_column_decoder()

    def add_modules(self):
        debug.info(1, "Add sram modules")
        self.right_bank_inst = self.bank_inst = self.add_bank(0, vector(0, 0), x_flip=0, y_flip=0)
        self.bank_insts = [self.right_bank_inst]
        self.add_col_decoder()
        self.add_row_decoder()
        self.add_power_rails()
        if self.num_banks == 2:
            x_offset = self.get_left_bank_x()
            self.left_bank_inst = self.add_bank(1, vector(x_offset, 0), x_flip=0, y_flip=-1)
            self.bank_insts = [self.right_bank_inst, self.left_bank_inst]

    def route_layout(self):
        debug.info(1, "Route sram")
        self.route_column_decoder()
        self.route_row_decoder_clk()
        self.route_decoder_power()
        self.route_decoder_outputs()
        self.join_bank_controls()
        self.route_left_bank_power()
        self.route_power_grid()

        self.copy_layout_pins()

    def create_bank(self):
        self.bank = CmosBank(name="bank", word_size=self.word_size, num_words=self.num_words_per_bank,
                             words_per_row=self.words_per_row, num_banks=self.num_banks)
        self.add_mod(self.bank)
        if self.num_banks == 2:
            debug.info(1, "Creating left bank")
            self.left_bank = CmosBank(name="left_bank", word_size=self.word_size,
                                      num_words=self.num_words_per_bank,
                                      words_per_row=self.words_per_row,
                                      num_banks=self.num_banks,
                                      adjacent_bank=self.bank)
            self.add_mod(self.left_bank)

    def create_column_decoder_modules(self):
        buffer_sizes = [OPTS.predecode_sizes[0]] + OPTS.column_decoder_buffers[1:]
        if self.words_per_row == 2:
            self.column_decoder = FlopBuffer(OPTS.control_flop, OPTS.column_decoder_buffers)
        elif self.words_per_row == 4:
            self.column_decoder = hierarchical_predecode2x4(use_flops=True, buffer_sizes=buffer_sizes)
        else:
            self.column_decoder = hierarchical_predecode3x8(use_flops=True, buffer_sizes=buffer_sizes)

    def create_column_decoder(self):
        if self.words_per_row < 2:
            return
        self.create_column_decoder_modules()
        if self.words_per_row == 2:
            column_decoder = self.column_decoder
            column_decoder.pins = ["din", "clk", "dout", "dout_bar", "vdd", "gnd"]
            column_decoder.copy_layout_pin(column_decoder.buffer_inst, "out_inv", "dout_bar")
            self.col_decoder_connections = ["ADDR[{}]".format(self.bank_addr_size - 1), "clk_buf_1",
                                            "sel[1]", "sel[0]", "vdd", "gnd"]
        else:
            self.col_decoder_connections = []
            for i in reversed(range(self.col_addr_size)):
                self.col_decoder_connections.append("ADDR[{}]".format(self.bank_addr_size - 1 - i))
            for i in range(self.words_per_row):
                self.col_decoder_connections.append("sel[{}]".format(i))
            self.col_decoder_connections.extend(["clk_buf_1", "vdd", "gnd"])

        self.add_mod(self.column_decoder)

    def add_pins(self):
        for j in range(self.num_banks):
            for i in range(self.word_size):
                self.add_pin("DATA_{0}[{1}]".format(j + 1, i))
                if self.bank.has_mask_in:
                    self.add_pin("MASK_{0}[{1}]".format(j + 1, i))
        for i in range(self.bank_addr_size):
            self.add_pin("ADDR[{0}]".format(i))
        for pin in self.bank.control_buffers.get_input_pin_names() + ["vdd", "gnd"]:
            self.add_pin(pin)

    def copy_layout_pins(self):

        right_bank = self.bank_insts[0]
        for pin_name in self.bank.control_buffers.get_input_pin_names():
            self.copy_layout_pin(right_bank, pin_name)

        for i in range(self.row_addr_size):
            self.copy_layout_pin(self.row_decoder_inst, "A[{}]".format(i), "ADDR[{}]".format(i))
        if self.bank.has_mask_in:
            pin_names = ["DATA", "MASK"]
        else:
            pin_names = ["DATA"]

        for j in range(self.num_banks):
            for i in range(self.word_size):
                for pin_name in pin_names:
                    bit_index = j * self.word_size + i
                    self.copy_layout_pin(self.bank_insts[j], pin_name + "[{}]".format(i),
                                         "{0}[{1}]".format(pin_name, bit_index))

    def get_col_decoder_y(self):
        if self.words_per_row == 2:
            max_y_offset = self.bank.wordline_driver_inst.by() - self.wide_space
        else:

            # prevent clash with rails sel rails above decoder
            sel_rails_based_max_y = (self.bank.wordline_driver_inst.by() -
                                     self.bank.col_decoder_rail_space
                                     - self.column_decoder.height)

            # find flop nwell extension
            flop_nwells = self.column_decoder.flop.get_layer_shapes(NWELL, recursive=True)
            top_nwell = max(flop_nwells, key=lambda x: x.uy())
            flop_nwell_extension = top_nwell.uy() - self.column_decoder.flop.height

            wl_driver_buffer = self.bank.wordline_driver.logic_buffer.logic_mod
            wl_driver_nwell = max(wl_driver_buffer.get_layer_shapes(NWELL), key=lambda x: x.uy())
            wl_nwell_extension = wl_driver_nwell.uy() - wl_driver_buffer.height
            parallel_nwell_space = self.get_parallel_space(NWELL)

            max_y_offset = (self.bank.wordline_driver_inst.by() - self.column_decoder.height
                            - flop_nwell_extension - wl_nwell_extension - parallel_nwell_space -  # space above decoder
                            self.wide_space)  # space below decoder
            max_y_offset = min(max_y_offset, sel_rails_based_max_y)

        # bring it closer to the sel pins
        sel_pin_y = [self.bank.get_pin("sel[{}]".format(x)).cy() for x in range(self.words_per_row)]
        middle_y = sum(sel_pin_y) / self.words_per_row
        max_y_offset = min(middle_y - 0.5 * self.column_decoder.height, max_y_offset)
        if self.words_per_row > 2:
            # align one of the sel pins with the closest decoder output
            # find closest decoder output to sel_pins
            decoder_mux_pins = [(self.column_decoder.get_pin("out[{}]".format(x)),
                                 self.bank.get_pin("sel[{}]".format(x)), x)
                                for x in range(self.words_per_row)]
            # because we're shifting down, only decoder outputs above sel pins are candidates
            decoder_height = self.column_decoder.height  # subtract height because flipped vertically
            valid_pins = list(filter(lambda x: max_y_offset + (decoder_height - x[0].by()) > x[1].uy(),
                                     decoder_mux_pins))
            closest_pair = min(valid_pins, key=lambda x: abs(max_y_offset + (decoder_height - x[0].cy())
                                                             - x[1].cy()))
            decoder_pin, mux_pin, self.closest_decoder_pin_index = closest_pair
            # align bottom of pins if there is a mismatch
            if max_y_offset + (decoder_height - decoder_pin.uy()) > mux_pin.by():
                max_y_offset -= (max_y_offset + (decoder_height - decoder_pin.uy()) - mux_pin.by())
            max_y_offset += decoder_height  # for mirror
        return max_y_offset

    def add_col_decoder(self):
        if self.words_per_row == 1:
            return
        # check if there is enough space between row decoder and read_buf
        # if so, place above read_buf, otherwise, place to the left of read_buf
        if self.bank.col_decoder_is_left:
            left_most_rail_x = self.bank.read_buf_inst.lx() - 4 * self.bus_pitch
        else:
            left_most_rail_x = self.bank.leftmost_rail.offset.x
        column_decoder_y = (self.bank.bank_sel_buf_inst.by() +
                            (self.bank.col_decoder_y - self.bank.control_flop_y))

        column_decoder = self.column_decoder

        col_decoder_x = (left_most_rail_x - (1 + self.words_per_row) * self.bus_pitch -
                         column_decoder.width)
        self.column_decoder_inst = self.add_inst("col_decoder", mod=self.column_decoder,
                                                 offset=vector(col_decoder_x, column_decoder_y))
        self.connect_inst(self.col_decoder_connections)

    def get_left_bank_x(self):
        x_offset_by_wordline_driver = self.mid_gnd.lx() - self.wide_space - self.bank.width
        # find max control rail offset
        rail_offsets = [getattr(self.bank, rail_name + "_rail").lx() for rail_name in self.bank.rail_names]
        min_rail_x = min(rail_offsets)
        col_to_row_decoder_space = (self.words_per_row + 1) * self.m2_pitch
        if self.column_decoder_inst is not None:
            x_offset_by_col_decoder = (self.column_decoder_inst.lx() - col_to_row_decoder_space -
                                       (self.bank.width - min_rail_x))
            return min(x_offset_by_wordline_driver, x_offset_by_col_decoder)
        return x_offset_by_wordline_driver

    def add_row_decoder(self):

        left_most_rail_x = self.bank.leftmost_rail.offset.x
        if self.column_decoder_inst is not None:
            if self.bank.col_decoder_is_left:
                left_most_rail_x -= (1 + self.words_per_row) * self.bus_pitch
            else:
                left_most_rail_x -= self.words_per_row * self.bus_pitch
        elif self.bank.read_buf_inst.uy() < self.bank.control_buffers_inst.by():
            left_most_rail_x -= 2 * self.bus_pitch
        max_predecoder_x = (left_most_rail_x - self.get_wide_space(METAL2) -
                            self.row_decoder.width)
        max_row_decoder_x = self.bank.wordline_driver_inst.lx() - self.row_decoder.row_decoder_width
        x_offset = min(max_predecoder_x, max_row_decoder_x)

        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.row_decoder,
                                              offset=vector(x_offset, self.row_decoder_y))

        self.connect_inst(self.get_row_decoder_connections())

    def get_row_decoder_connections(self):
        temp = []
        for i in range(self.row_addr_size):
            temp.append("ADDR[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out[{0}]".format(j))
        temp.extend(["clk_buf_1", "vdd", "gnd"])
        return temp

    def add_power_rails(self):
        bank_vdd = self.bank.mid_vdd
        y_offset = bank_vdd.by()
        min_decoder_x = self.row_decoder_inst.lx()
        if self.column_decoder_inst is not None:
            min_decoder_x = min(min_decoder_x, self.column_decoder_inst.lx() - 2 * self.bus_pitch)
        x_offset = min_decoder_x - self.wide_space - bank_vdd.width()
        self.mid_vdd = self.add_rect(METAL2, offset=vector(x_offset, y_offset), width=bank_vdd.width(),
                                     height=bank_vdd.height())

        x_offset -= (self.get_wide_space(METAL2) + bank_vdd.width())
        self.mid_gnd = self.add_rect(METAL2, offset=vector(x_offset, y_offset), width=bank_vdd.width(),
                                     height=bank_vdd.height())

    def get_bank_connections(self, bank_num):
        connections = []
        for i in range(self.word_size):
            connections.append("DATA_{0}[{1}]".format(bank_num + 1, i))
            if self.bank.has_mask_in:
                connections.append("MASK_{0}[{1}]".format(bank_num + 1, i))

        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                connections.append("sel[{}]".format(i))
        for i in range(self.num_rows):
            connections.append("dec_out[{}]".format(i))

        bank_sel = "bank_sel"
        connections.extend(self.bank.control_buffers.get_input_pin_names() +
                           ["clk_buf_{}".format(bank_num + 1), "clk_bar_{}".format(bank_num + 1),
                            "vdd", "gnd"])
        return connections

    def route_row_decoder_clk(self):
        clk_rail = getattr(self.bank, "clk_buf_rail")

        decoder_clk_pins = self.row_decoder_inst.get_pins("clk")
        valid_decoder_pins = list(filter(lambda x: x.by() > clk_rail.by(), decoder_clk_pins))
        closest_clk = min(valid_decoder_pins, key=lambda x: abs(clk_rail.by() - x.by()))

        if self.bank.has_mask_in:
            top_mask_clock = max(self.bank.mask_in_flops_inst.get_pins("clk"), key=lambda x: x.cy())
        else:
            top_mask_clock = None

        predecoder_mod = (self.row_decoder.pre2x4_inst + self.row_decoder.pre3x8_inst)[0]
        predecoder_vdd_height = predecoder_mod.get_pins("vdd")[0].height()
        wide_space = self.get_line_end_space(METAL3)

        y_offset = closest_clk.by() + 0.5 * predecoder_vdd_height + wide_space

        if top_mask_clock and y_offset > top_mask_clock.by():
            y_offset = max(y_offset, top_mask_clock.cy() + wide_space)
            self.add_rect(METAL2, offset=clk_rail.ul(), width=clk_rail.width,
                          height=y_offset + m1m2.height - clk_rail.uy())
        via_y = y_offset + 0.5 * m1m2.height
        self.add_contact_center(m1m2.layer_stack, offset=vector(clk_rail.cx(), via_y))
        m1_y = y_offset + 0.5 * m1m2.height - 0.5 * self.m1_width
        self.add_rect(METAL1, offset=vector(closest_clk.lx(), m1_y),
                      width=clk_rail.cx() - closest_clk.lx())
        self.add_contact_center(m1m2.layer_stack, offset=vector(closest_clk.cx(), via_y))

    def route_column_decoder(self):
        if self.words_per_row < 2:
            return
        if self.words_per_row == 2:
            self.route_flop_column_decoder()
        else:
            self.route_predecoder_column_decoder()

    def route_flop_column_decoder(self):
        self.route_col_decoder_clock()

        # outputs
        out_pin = self.column_decoder_inst.get_pin("dout")
        out_bar_pin = self.column_decoder_inst.get_pin("dout_bar")
        y_offsets = [out_pin.cy(), out_pin.cy() + self.bus_pitch]
        self.col_decoder_outputs = []

        self.route_col_decoder_to_rail(output_pins=[out_bar_pin, out_pin], rail_offsets=y_offsets)

        self.route_col_decoder_outputs()
        self.route_col_decoder_power()
        self.copy_layout_pin(self.column_decoder_inst, "din", "ADDR[{}]".format(self.addr_size - self.num_banks))

    def route_col_decoder_clock(self):
        # route clk
        row_decoder_clk = min(self.row_decoder_inst.get_pins("clk"), key=lambda x: x.cy())
        row_decoder_vdd = min(self.row_decoder_inst.get_pins("vdd"), key=lambda x: x.cy())
        decoder_clk_y = row_decoder_vdd.by() - self.bus_pitch
        self.add_rect(METAL2, offset=vector(row_decoder_clk.lx(), decoder_clk_y), width=row_decoder_clk.width(),
                      height=row_decoder_clk.by() - decoder_clk_y)
        self.add_cross_contact_center(cross_m2m3, offset=vector(row_decoder_clk.cx(),
                                                                decoder_clk_y + 0.5 * self.bus_width))
        x_offset = self.column_decoder_inst.lx() - self.bus_pitch
        self.add_rect(METAL3, offset=vector(x_offset, decoder_clk_y), height=self.bus_width,
                      width=row_decoder_clk.cx() - x_offset)
        col_decoder_clk = self.column_decoder_inst.get_pin("clk")
        self.add_cross_contact_center(cross_m2m3, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                decoder_clk_y + 0.5 * self.bus_width))
        y_offset = col_decoder_clk.cy() - 0.5 * self.bus_width
        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=decoder_clk_y - y_offset,
                      width=self.bus_width)
        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=self.bus_width,
                      width=col_decoder_clk.lx() - x_offset)
        if col_decoder_clk.layer == METAL1:
            self.add_contact(m1m2.layer_stack, offset=vector(col_decoder_clk.lx(),
                                                             col_decoder_clk.cy() - 0.5 * m1m2.width),
                             rotate=90)

    def route_col_decoder_to_rail(self, output_pins=None, rail_offsets=None):
        if output_pins is None:
            output_pins = [self.column_decoder_inst.get_pin("out[{}]".format(i)) for i in range(self.words_per_row)]
        if rail_offsets is None:
            rail_offsets = [x.cy() for x in output_pins]

        if self.bank.col_decoder_is_left:
            base_x = self.column_decoder_inst.rx() + self.bus_pitch
            # using by() because mirror
            base_y = (self.bank.read_buf_inst.by() + self.bank.rail_space_above_controls
                      - self.words_per_row * self.bus_pitch)
            rails_y = [base_y + i * self.bus_pitch for i in range(self.words_per_row)]

            x_offset = self.bank.leftmost_rail.offset.x - (1 + self.words_per_row) * self.bus_pitch
            rails_x = [x_offset + i * self.bus_pitch for i in range(self.words_per_row)]
        else:
            base_x = self.bank.leftmost_rail.offset.x - self.words_per_row * self.bus_pitch
            rails_y = []
            rails_x = []
        x_offsets = [base_x + i * self.bus_pitch for i in range(self.words_per_row)]

        self.col_decoder_outputs = []
        for i in range(self.words_per_row):
            output_pin = output_pins[i]
            x_offset = x_offsets[i]
            y_offset = rail_offsets[i]
            if i == 0 and self.words_per_row == 2:
                self.add_contact_center(m1m2.layer_stack,
                                        offset=vector(output_pin.cx(),
                                                      y_offset + 0.5 * self.bus_width))
                self.add_rect(METAL2, offset=vector(output_pin.cx(), y_offset),
                              height=self.bus_width, width=x_offset - output_pin.cx())
            else:
                self.add_rect(METAL1, offset=vector(output_pin.cx(), y_offset),
                              width=x_offset - output_pin.cx(),
                              height=self.bus_width)
                self.add_cross_contact_center(cross_m1m2,
                                              offset=vector(x_offset + 0.5 * self.bus_width,
                                                            y_offset + 0.5 * self.bus_width),
                                              rotate=True)
            if not self.bank.col_decoder_is_left:
                self.col_decoder_outputs.append(self.add_rect(METAL2,
                                                              offset=vector(x_offset, y_offset),
                                                              width=self.bus_width,
                                                              height=self.bus_width))
            else:
                _, fill_height = self.calculate_min_area_fill(self.bus_width, layer=METAL2)
                rail_y = rails_y[i]
                m2_height = rail_y - y_offset
                self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                              height=m2_height, width=self.bus_width)

                if abs(m2_height) < fill_height:
                    self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=fill_height, width=self.bus_width)

                self.add_cross_contact_center(cross_m2m3, offset=vector(x_offset + 0.5 * self.bus_width,
                                                                        rail_y + 0.5 * self.bus_width))
                self.add_rect(METAL3, offset=vector(x_offset, rail_y), width=rails_x[i] - x_offset,
                              height=self.bus_width)
                self.add_cross_contact_center(cross_m2m3, offset=vector(rails_x[i] + 0.5 * self.bus_width,
                                                                        rail_y + 0.5 * self.bus_width))
                self.col_decoder_outputs.append(self.add_rect(METAL2, offset=vector(rails_x[i], rail_y),
                                                              width=self.bus_width, height=self.bus_width))

    def route_col_decoder_outputs(self):
        if self.num_banks == 2:
            top_predecoder_inst = max(self.row_decoder.pre2x4_inst + self.row_decoder.pre3x8_inst,
                                      key=lambda x: x.uy())
            # place rails just above the input flops
            num_flops = top_predecoder_inst.mod.num_inputs
            y_space = top_predecoder_inst.get_pins("vdd")[0].height() + self.get_wide_space(METAL3) + self.bus_space
            self.left_col_mux_select_y = (self.row_decoder_inst.by() + top_predecoder_inst.by()
                                          + num_flops * top_predecoder_inst.mod.flop.height + y_space)

        for i in range(self.words_per_row):
            sel_pin = self.right_bank_inst.get_pin("sel[{}]".format(i))
            rail = self.col_decoder_outputs[i]
            self.add_rect(METAL2, offset=rail.ul(), width=self.bus_width,
                          height=sel_pin.cy() - rail.uy())
            self.add_rect(METAL1, offset=vector(rail.lx(), sel_pin.cy() - 0.5 * self.bus_width),
                          width=sel_pin.lx() - rail.lx(), height=self.bus_width)
            self.add_cross_contact_center(cross_m1m2, offset=vector(rail.cx(), sel_pin.cy()),
                                          rotate=True)

            if self.num_banks == 2:
                # route to the left
                x_start = self.left_bank_inst.rx() - self.left_bank.leftmost_rail.offset.x
                x_offset = x_start + (1 + i) * self.bus_pitch

                y_offset = self.left_col_mux_select_y + i * self.bus_pitch
                self.add_rect(METAL2, offset=vector(rail.lx(), sel_pin.cy()), width=self.bus_width,
                              height=y_offset - sel_pin.cy())
                self.add_cross_contact_center(cross_m2m3,
                                              offset=vector(rail.cx(),
                                                            y_offset + 0.5 * self.bus_width))
                self.add_rect(METAL3, offset=vector(x_offset, y_offset), height=self.bus_width,
                              width=rail.lx() - x_offset)
                self.add_cross_contact_center(cross_m2m3,
                                              offset=vector(x_offset + 0.5 * self.bus_width,
                                                            y_offset + 0.5 * self.bus_width))
                sel_pin = self.left_bank_inst.get_pin("sel[{}]".format(i))
                self.add_rect(METAL2, offset=vector(x_offset, sel_pin.cy()), width=self.bus_width,
                              height=y_offset - sel_pin.cy())
                self.add_cross_contact_center(cross_m1m2,
                                              offset=vector(x_offset + 0.5 * self.bus_width,
                                                            sel_pin.cy()), rotate=True)
                self.add_rect(METAL1, offset=sel_pin.lr(), height=sel_pin.height(),
                              width=x_offset - sel_pin.rx())

    def route_right_bank_sel_in(self, sel_offsets):
        """
        route sel pins from col decoder to the bank on the right
        :param sel_offsets: arranged from sel_0 to sel_x
        """
        y_bend = (self.bank.wordline_driver_inst.by() - self.bank.col_decoder_rail_space +
                  self.m3_pitch)
        x_bend = (self.row_decoder_inst.lx() + self.row_decoder.width +
                  self.words_per_row * self.m2_pitch + 2 * self.wide_space)
        for i in range(len(sel_offsets)):
            in_pin = self.bank_insts[0].get_pin("sel[{}]".format(i))
            x_offset = sel_offsets[i]
            self.add_rect(METAL2, offset=vector(x_offset, in_pin.by()), height=y_bend - in_pin.by())
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset,
                                                             y_bend + self.m3_width - m2m3.height))

            self.add_rect(METAL3, offset=vector(x_offset, y_bend), width=x_bend - x_offset)

            self.add_contact(m2m3.layer_stack, offset=vector(x_bend + m2m3.height, y_bend),
                             rotate=90)
            in_pin = self.bank_insts[0].get_pin("sel[{}]".format(i))
            self.add_rect(METAL2, offset=vector(x_bend, in_pin.by()), height=y_bend - in_pin.by())
            self.add_contact(m1m2.layer_stack, offset=vector(x_bend, in_pin.by()))
            self.add_rect(METAL1, offset=vector(x_bend, in_pin.by()), width=in_pin.lx() - x_bend)

            y_bend += self.m3_pitch
            x_bend -= self.m2_pitch

    def route_predecoder_column_decoder(self):

        # assumes predecoders are wider than the control_flops below it
        # address pins
        all_addr_pins = ["ADDR[{}]".format(self.addr_size - 1 - i) for i in range(self.col_addr_size)]
        all_addr_pins = list(reversed(all_addr_pins))
        for i in range(self.col_addr_size):
            col_decoder_pin = self.column_decoder_inst.get_pin("flop_in[{}]".format(i))
            self.add_layout_pin(all_addr_pins[i], METAL2, offset=vector(col_decoder_pin.lx(), self.min_point),
                                height=col_decoder_pin.by() - self.min_point)

        # sel pins
        if self.single_bank:
            x_offset = self.column_decoder_inst.rx() + self.wide_space
        else:
            x_offset = self.column_decoder_inst.lx() - self.wide_space - self.m2_width

        sel_offsets = []

        for i in range(self.words_per_row):
            out_pin = self.column_decoder_inst.get_pin("out[{}]".format(i))
            in_pin = self.bank_insts[self.num_banks - 1].get_pin("sel[{}]".format(i))

            in_pin_x = in_pin.lx() if self.single_bank else in_pin.rx()
            if i == self.closest_decoder_pin_index:
                self.add_rect(METAL1, offset=vector(out_pin.lx(), in_pin.by()),
                              width=in_pin_x - out_pin.lx())
            else:
                y_offset = out_pin.cy() - 0.5 * self.m1_width

                self.add_rect(METAL1, offset=vector(out_pin.rx(), y_offset),
                              width=x_offset - out_pin.rx() + self.m1_width)
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset + 0.5 * m1m2.width,
                                                                        y_offset + 0.5 * self.m1_width))
                m2_height = in_pin.by() - y_offset
                self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=m2_height)

                if i < self.closest_decoder_pin_index:
                    self.add_contact(m1m2.layer_stack, offset=vector(x_offset, in_pin.by()))
                else:
                    self.add_contact(m1m2.layer_stack, offset=vector(x_offset, in_pin.by() - m1m2.height))
                rail_x = x_offset if self.single_bank else x_offset + self.m1_width
                self.add_rect(METAL1, offset=vector(rail_x, in_pin.by()), width=in_pin_x - rail_x)
            if not self.single_bank:
                # route to right bank
                if i == self.closest_decoder_pin_index:
                    self.add_contact(m1m2.layer_stack,
                                     offset=vector(x_offset, in_pin.by() + self.m1_width - m1m2.height))
                sel_offsets.append(x_offset)
                self.route_right_bank_sel_in(sel_offsets)

            if not self.single_bank or not i == self.closest_decoder_pin_index:
                x_offset += self.m2_pitch if self.single_bank else -self.m2_pitch

        # clk
        col_decoder_clk = self.column_decoder_inst.get_pin("clk")
        if self.single_bank:
            row_decoder_clks = self.row_decoder_inst.get_pins("clk")
            closest_clk = list(filter(lambda x: x.by() <= col_decoder_clk.by() <= x.uy(),
                                      row_decoder_clks))
            if not closest_clk:
                closest_clk = min(row_decoder_clks, key=lambda x: x.by())
            else:
                closest_clk = closest_clk[0]
            self.add_rect(METAL2, offset=vector(closest_clk.lx(), col_decoder_clk.by()),
                          width=col_decoder_clk.lx() - closest_clk.lx())
        else:
            # find clk rail
            clk_rail = getattr(self.bank, "clk_buf_rail")
            clk_rail_x = self.bank_insts[1].rx() - (clk_rail.rx())
            mask_in_pin = self.bank.mask_in_flops_inst.get_pin("clk")
            y_offset = mask_in_pin.cy() - 0.5 * m2m3.height
            x_offset = col_decoder_clk.lx()
            self.add_contact(m2m3.layer_stack, offset=vector(clk_rail_x, y_offset))

            self.add_rect(METAL3, offset=vector(clk_rail_x, mask_in_pin.by()), width=x_offset - clk_rail_x)
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, y_offset))
            self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                          height=col_decoder_clk.by() - y_offset)

        # vdd and gnd
        col_decoder_vdd_pins = self.column_decoder_inst.get_pins("vdd")
        row_decoder_vdd = self.row_decoder_inst.get_pins("vdd")
        top_col_vdd = max(col_decoder_vdd_pins, key=lambda x: x.uy())
        closest_row_vdd = min(row_decoder_vdd, key=lambda x: abs(x.cy() - top_col_vdd.cy()))

        up = "up"
        down = "down"

        direction = up if closest_row_vdd.cy() >= top_col_vdd.cy() else down

        def find_closest_row_pin(col_pin, pin_name_):
            row_decoder_pins = self.row_decoder_inst.get_pins(pin_name_)
            if direction == up:
                valid = list(filter(lambda x: x.cy() >= col_pin.cy(), row_decoder_pins))
            else:
                valid = list(filter(lambda x: x.cy() < col_pin.cy(), row_decoder_pins))
            if not valid:
                return None
            closest = min(valid, key=lambda x: abs(x.cy() - col_pin.cy()))
            # predecoder vdd's may overlap, find the rightmost one
            overlapped_pins = list(filter(lambda x: x.cy() == closest.cy(), row_decoder_pins))
            return max(overlapped_pins, key=lambda x: x.rx())

        for pin_name in ["vdd", "gnd"]:
            for pin in self.column_decoder_inst.get_pins(pin_name):
                closest_row_pin = find_closest_row_pin(pin, pin_name)
                rail = getattr(self, "mid_" + pin_name)

                if closest_row_pin is None:

                    flop_vdd_extension = max(self.column_decoder.flop.get_pin("vdd").uy() -
                                             self.column_decoder.flop.height,
                                             self.column_decoder.inv.get_pin("vdd").uy() -
                                             self.column_decoder.inv.height)
                    y_offset = min(pin.by(), self.row_decoder_inst.by() - flop_vdd_extension -
                                   pin.height() - self.wide_space)
                    x_offset = pin.lx() if self.single_bank else pin.rx()
                    self.add_rect(METAL1, offset=vector(rail.lx(), y_offset), height=pin.height(),
                                  width=x_offset - rail.lx())
                    if y_offset < pin.by():
                        self.add_rect(METAL1, offset=vector(x_offset, y_offset), width=pin.height(),
                                      height=pin.by() - y_offset)
                    via_x = 0.5 * (rail.lx() + rail.rx())
                    self.add_contact_center(m1m2.layer_stack, offset=vector(via_x,
                                                                            y_offset + 0.5 * pin.height()),
                                            size=[2, 1], rotate=90)
                    continue

                if closest_row_pin.uy() > self.bank.wordline_driver_inst.by() and pin_name == "vdd":
                    # this is a vdd, so just add all the way to wordline drivers
                    self.add_rect(METAL1, offset=pin.ul(),
                                  height=closest_row_pin.by() - pin.uy(), width=pin.height())
                    continue

                if self.single_bank:
                    x_offset = pin.lx() - self.wide_space - pin.height()
                    self.add_rect(METAL1, offset=vector(x_offset, pin.by()),
                                  height=pin.height(), width=pin.lx() - x_offset)

                    if direction == up:
                        y_bend = closest_row_pin.by() - pin.height() - self.wide_space
                    else:
                        y_bend = closest_row_pin.uy() + pin.height() + self.wide_space

                    self.add_rect(METAL1, offset=vector(x_offset, pin.by()), height=y_bend - pin.by(),
                                  width=pin.height())
                    closest_x = closest_row_pin.rx() - pin.height()
                    self.add_rect(METAL1, offset=vector(closest_x, y_bend), height=pin.height(),
                                  width=x_offset + pin.height() - closest_x)
                    self.add_rect(METAL1, offset=vector(closest_x, y_bend), width=pin.height(),
                                  height=closest_row_pin.cy() - y_bend)
                else:
                    x_offset = pin.rx() + self.wide_space
                    # add a jut to move away from potential clash to the right
                    jut = pin.height() + self.wide_space
                    if abs(pin.cy() - closest_row_pin.cy()) < jut:
                        jut = 0
                        y_bend = pin.by()
                    elif direction == up:
                        y_bend = pin.uy() + jut
                    else:
                        y_bend = pin.by() - jut
                    jut_x = pin.rx() - pin.height()
                    if jut > 0:
                        self.add_rect(METAL1, offset=vector(jut_x, pin.cy()),
                                      width=pin.height(), height=y_bend - pin.cy())
                    self.add_rect(METAL1, offset=vector(jut_x, y_bend), height=pin.height(),
                                  width=x_offset + pin.height() - jut_x)
                    self.add_rect(METAL1, offset=vector(x_offset, y_bend), width=pin.height(),
                                  height=closest_row_pin.cy() - y_bend)
                    self.add_rect(METAL1, offset=vector(x_offset, closest_row_pin.by()),
                                  height=closest_row_pin.height(), width=rail.lx() - x_offset)

    def route_decoder_power(self):
        rails = [self.mid_vdd, self.mid_gnd]
        pin_names = ["vdd", "gnd"]
        for i in range(2):
            rail = rails[i]
            center_rail_x = 0.5 * (rail.lx() + rail.rx())
            power_pins = self.row_decoder_inst.get_pins(pin_names[i])
            for power_pin in power_pins:
                if power_pin.uy() < self.bank.wordline_driver_inst.by():
                    pin_right = power_pin.rx()
                    x_offset = rail.lx()
                else:
                    pin_right = self.bank.wordline_driver_inst.lx()
                    x_offset = rail.lx() if self.single_bank else self.left_bank_inst.rx()
                self.add_rect(METAL1, offset=vector(x_offset, power_pin.by()),
                              width=pin_right - x_offset, height=power_pin.height())
                self.add_contact_center(m1m2.layer_stack, offset=vector(center_rail_x, power_pin.cy()),
                                        size=[2, 1], rotate=90)

        via_offsets, fill_height = self.evaluate_left_power_rail_vias()
        self.add_left_power_rail_vias(via_offsets, self.mid_vdd.uy(), fill_height)

    def evaluate_left_power_rail_vias(self):
        # find locations for
        fill_width = self.mid_vdd.width
        _, fill_height = self.calculate_min_area_fill(fill_width, min_height=self.m3_width,
                                                      layer=METAL3)

        wide_space = self.get_wide_space(METAL3)
        via_spacing = wide_space + self.parallel_via_space
        via_pitch = via_spacing + max(m2m3.height, fill_height)

        m2_m3_blockages = []

        if self.num_banks == 2 and self.column_decoder_inst is not None:
            # prevent select pins clash
            m2_m3_blockages.append((self.left_col_mux_select_y,
                                    self.bank.bitcell_array_inst.by()))

        if self.num_banks == 2:
            # prevent clashes with wl output to left bank
            row_decoder_gnd = self.row_decoder_inst.get_pins("gnd")
            row_decoder_gnd = [x for x in row_decoder_gnd
                               if x.by() > self.bank.bitcell_array_inst.by()]
            wl_space = self.get_parallel_space(METAL3)
            for gnd_pin in row_decoder_gnd:
                m2_m3_blockages.append((gnd_pin.by() - wl_space - self.m3_width,
                                        gnd_pin.uy() + wide_space + self.m3_width))

        m2_m3_blockages = list(sorted(m2_m3_blockages, key=lambda x: x[0]))
        via_top = self.mid_vdd.height - via_pitch
        via_offsets = []
        y_offset = self.bank.bank_sel_buf_inst.by()

        while y_offset < via_top:
            if len(m2_m3_blockages) > 0 and m2_m3_blockages[0][0] <= y_offset + via_pitch:
                y_offset = m2_m3_blockages[0][1] + via_pitch
                m2_m3_blockages.pop(0)
            else:
                via_offsets.append(y_offset)
                y_offset += via_pitch
        return via_offsets, fill_height

    def add_left_power_rail_vias(self, via_offsets, rail_top, fill_height):
        m4_power_pins = self.right_bank_inst.get_pins("vdd") + self.right_bank_inst.get_pins("gnd")
        if self.num_banks == 2:
            m4_power_pins.extend(self.left_bank_inst.get_pins("vdd") + self.left_bank_inst.get_pins("gnd"))
        m4_power_pins = [x for x in m4_power_pins if x.layer == METAL4]

        self.m4_vdd_rects = []
        self.m4_gnd_rects = []
        rails = [self.mid_vdd, self.mid_gnd]
        fill_width = self.mid_vdd.width

        for i in range(2):
            rail = rails[i]
            for y_offset in via_offsets:
                via_offset = vector(rail.cx(), y_offset + 0.5 * fill_height)
                self.add_contact_center(m2m3.layer_stack, offset=via_offset,
                                        size=[1, 2], rotate=90)
                self.add_contact_center(m3m4.layer_stack, offset=via_offset,
                                        size=[1, 2], rotate=90)
                self.add_rect_center(METAL3, offset=via_offset, width=fill_width,
                                     height=fill_height)

            rect = self.add_rect(METAL4, offset=rail.ll(),
                                 width=rail.width, height=rail_top - rail.by())
            if i % 2 == 0:
                self.m4_vdd_rects.append(rect)
            else:
                self.m4_gnd_rects.append(rect)

        self.m4_power_pins = m4_power_pins

    def route_col_decoder_power(self):
        rails = [self.mid_vdd, self.mid_gnd]
        pin_names = ["vdd", "gnd"]
        for i in range(2):
            pin_name = pin_names[i]
            if self.words_per_row == 2:
                y_shift = self.column_decoder_inst.by() + self.column_decoder.flop_inst.by()
                x_shift = self.column_decoder_inst.lx() + self.column_decoder.flop_inst.lx()
                pins = self.column_decoder.flop.get_pins(pin_name)

                for pin in pins:
                    via = m2m3 if pin.layer == METAL3 else m1m2
                    pin_y = pin.by() + y_shift
                    self.add_rect(pin.layer, offset=vector(rails[i].lx(), pin_y),
                                  height=pin.height(), width=pin.lx() + x_shift - rails[i].lx())
                    self.add_contact_center(via.layer_stack,
                                            offset=vector(rails[i].cx(), pin_y + 0.5 * pin.height()),
                                            size=[1, 2], rotate=90)
            else:
                flop_height = self.column_decoder.flop.height
                for pin in self.column_decoder_inst.get_pins(pin_name):

                    if pin.by() - self.column_decoder_inst.by() > self.col_addr_size * flop_height:
                        x_right = pin.lx()
                        via = m1m2
                        layer = METAL1
                    else:
                        x_right = self.column_decoder_inst.lx() + self.column_decoder.in_inst[0].lx()
                        via = m2m3
                        layer = METAL3
                    self.add_rect(layer, offset=vector(rails[i].lx(), pin.by()),
                                  width=x_right - rails[i].lx(), height=pin.height())
                    self.add_contact_center(via.layer_stack, offset=vector(rails[i].cx(), pin.cy()),
                                            size=[1, 2], rotate=90)

    def route_left_bank_power(self):
        if self.num_banks == 1:
            return
        debug.info(1, "Route left bank sram power")
        rails = [self.mid_gnd, self.mid_vdd]
        pin_names = ["gnd", "vdd"]
        for i in range(2):
            rail = rails[i]
            for pin in self.left_bank.wordline_driver_inst.get_pins(pin_names[i]):
                if not pin.layer == METAL3:
                    continue
                pin_x = self.left_bank_inst.rx() - pin.lx()
                self.add_rect(METAL3, offset=vector(pin_x, pin.by()), height=pin.height(),
                              width=rail.rx() - pin_x)
                self.add_contact_center(m2m3.layer_stack, offset=vector(rail.cx(), pin.cy()),
                                        rotate=90, size=[1, 2])

    def route_decoder_outputs(self):
        # place m3 rail to the bank wordline drivers just below the power rail
        buffer_mod = self.bank.wordline_driver.logic_buffer
        gnd_pin = buffer_mod.get_pin("gnd")

        odd_rail_y = gnd_pin.uy() + self.get_parallel_space(METAL3)
        even_rail_y = buffer_mod.height - odd_rail_y - self.m3_width
        fill_height = m2m3.height
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)

        for row in range(self.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            wl_ins = [self.right_bank_inst.get_pin("dec_out[{}]".format(row))]
            if not self.single_bank:
                wl_ins.append(self.left_bank_inst.get_pin("dec_out[{}]".format(row)))

            if row % 2 == 0:
                via_y = decoder_out.uy() - 0.5 * m2m3.second_layer_height
                rail_y = even_rail_y
            else:
                via_y = decoder_out.by() - 0.5 * m2m3.second_layer_height
                rail_y = odd_rail_y

            via_offset = vector(decoder_out.cx() - 0.5 * self.m3_width, via_y)

            self.add_contact(m2m3.layer_stack, offset=via_offset)
            y_offset = self.bank.wordline_driver_inst.by() + row * buffer_mod.height + rail_y
            self.add_rect(METAL3, offset=via_offset, height=y_offset - via_offset.y)
            if self.num_banks == 1:
                x_offset = via_offset.x
            else:
                x_offset = wl_ins[1].cx() - 0.5 * self.m3_width
            self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                          width=wl_ins[0].cx() + 0.5 * self.m3_width - x_offset)

            for i in range(len(wl_ins)):
                wl_in = wl_ins[i]
                x_offset = wl_in.cx() - 0.5 * self.m3_width
                self.add_rect(METAL3, offset=vector(x_offset, wl_in.cy()),
                              height=y_offset - wl_in.cy())
                self.add_contact_center(m2m3.layer_stack, wl_in.center())
                self.add_contact_center(m1m2.layer_stack, wl_in.center())
                if fill_width > 0:
                    self.add_rect_center(METAL2, offset=wl_in.center(), width=fill_width,
                                         height=fill_height)

    def join_bank_controls(self):
        if self.single_bank:
            return
        pin_names = self.bank.control_buffers.get_input_pin_names()
        bottom_inst_y = self.bank.bank_sel_buf_inst.by()
        if self.column_decoder_inst is not None:
            bottom_inst_y = min(bottom_inst_y, self.column_decoder_inst.by())
        cross_clk_rail_y = (bottom_inst_y - self.get_wide_space(METAL2)
                            - self.bus_pitch)
        y_offset = cross_clk_rail_y - (len(pin_names) + 1) * self.bus_pitch
        via_extension = 0.5 * (cross_m2m3.height - cross_m2m3.contact_width)
        for i in range(len(pin_names)):
            left_pin = self.bank_insts[1].get_pin(pin_names[i])
            right_pin = self.bank_insts[0].get_pin(pin_names[i])
            for pin in [left_pin, right_pin]:
                self.add_cross_contact_center(cross_m2m3,
                                              offset=vector(pin.cx(),
                                                            y_offset + 0.5 * self.bus_width))
                rail_bottom = y_offset + 0.5 * self.bus_width - 0.5 * cross_m2m3.height
                if rail_bottom < pin.by():
                    self.add_rect(pin.layer, offset=vector(pin.lx(), rail_bottom),
                                  width=pin.width(), height=pin.by() - rail_bottom)
            self.add_rect(METAL3, offset=vector(left_pin.lx() - via_extension, y_offset),
                          height=self.bus_width,
                          width=right_pin.rx() - left_pin.lx() + 2 * via_extension)

            y_offset += self.bus_pitch

    def route_power_grid(self):
        if not self.add_power_grid or True:
            for i in range(self.num_banks):
                self.copy_layout_pin(self.bank_insts[i], "vdd")
                self.copy_layout_pin(self.bank_insts[i], "gnd")
            return

        debug.info(1, "Route sram power grid")
        metal_layers, layer_numbers = utils.get_sorted_metal_layers()
        top_layer = metal_layers[-1]
        second_top_layer = metal_layers[-2]

        # second_top to top layer via
        m_top_via = ContactFullStack(start_layer=-2, stop_layer=-1, centralize=False)
        # m4 to second_top layer vias
        all_m4_power_pins = self.m4_power_pins + self.m4_gnd_rects + self.m4_vdd_rects
        all_m4_power_widths = list(set([utils.round_to_grid(x.rx() - x.lx()) for x in all_m4_power_pins]))
        all_m4_vias = {}
        for width in all_m4_power_widths:
            all_m4_vias[width] = ContactFullStack(start_layer=3, stop_layer=-2, centralize=True,
                                                  max_width=width)
        # dimensions of vertical top layer grid
        left = min(map(lambda x: x.lx(), all_m4_power_pins)) - 0.5 * m_top_via.width
        right = max(map(lambda x: x.rx(), all_m4_power_pins)) - 0.5 * m_top_via.width
        bottom = min(map(lambda x: x.by(), all_m4_power_pins))
        top = max(map(lambda x: x.uy(), all_m4_power_pins)) - m_top_via.height

        # add top layer
        top_layer_width = m_top_via.width
        top_layer_space = self.get_wide_space(top_layer)
        top_layer_pitch = top_layer_width + top_layer_space
        top_layer_pins = []

        x_offset = left
        i = 0
        while x_offset < right:
            pin_name = "gnd" if i % 2 == 0 else "vdd"
            top_layer_pins.append(self.add_layout_pin(pin_name, top_layer, offset=vector(x_offset, bottom),
                                                      width=top_layer_width, height=top - bottom))
            x_offset += top_layer_pitch
            i += 1
        top_gnd = top_layer_pins[0::2]
        top_vdd = top_layer_pins[1::2]

        # add second_top layer
        y_offset = bottom
        rail_height = max(map(lambda x: x.height, [m_top_via] + list(all_m4_vias.values())))
        rail_space = self.get_wide_space(second_top_layer)
        rail_pitch = rail_height + rail_space

        m4_vdd_rects = self.m4_vdd_rects + [x for x in self.m4_power_pins if x.name == "vdd"]
        m4_vdd_rects = list(sorted(m4_vdd_rects, key=lambda x: x.lx()))
        m4_gnd_rects = self.m4_gnd_rects + [x for x in self.m4_power_pins if x.name == "gnd"]
        m4_gnd_rects = list(sorted(m4_gnd_rects, key=lambda x: x.lx()))

        i = 0
        while y_offset < top - m_top_via.height:
            rail_rect = self.add_rect(second_top_layer, offset=vector(left, y_offset), height=rail_height,
                                      width=right + m_top_via.width - left)
            # connect to top grid
            top_pins = top_gnd if i % 2 == 0 else top_vdd
            for top_pin in top_pins:
                self.add_inst(m_top_via.name, m_top_via,
                              offset=vector(top_pin.lx(), rail_rect.cy() - 0.5 * m_top_via.height))
                self.connect_inst([])

            # connect to m4 below
            m4_rects = m4_gnd_rects if i % 2 == 0 else m4_vdd_rects
            x_offset = m4_rects[0].lx()
            for m4_rect in m4_rects:
                if m4_rect.by() < y_offset and m4_rect.uy() > rail_rect.uy():
                    if m4_rect.lx() < x_offset:  # prevent via clash
                        continue
                    m4_rect_width = utils.round_to_grid(m4_rect.rx() - m4_rect.lx())
                    m4_via = all_m4_vias[m4_rect_width]
                    self.add_inst(m4_via.name, mod=m4_via,
                                  offset=vector(m4_rect.cx(), rail_rect.cy() - 0.5 * m4_via.height))
                    self.connect_inst([])
                    x_offset = m4_rect.cx() + 0.5 * m4_via.width + rail_space

            y_offset += rail_pitch
            i += 1

    def add_lvs_correspondence_points(self):
        pass

    def add_cross_contact_center(self, cont, offset, rotate=False,
                                 rail_width=None):
        super().add_cross_contact_center(cont, offset, rotate)
        self.add_cross_contact_center_fill(cont, offset, rotate, rail_width)
