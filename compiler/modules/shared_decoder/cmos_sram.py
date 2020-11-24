import debug
from base import utils
from base.contact import m1m2, m2m3
from base.design import METAL1, METAL2, NWELL, METAL3
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
        self.row_decoder_y = (self.bank.bitcell_array_inst.uy() - self.row_decoder.height
                              - self.bank.bitcell.height)
        self.create_column_decoder()

    def add_modules(self):
        debug.info(1, "Add sram modules")
        self.right_bank_inst = self.bank_inst = self.add_bank(0, vector(0, 0), x_flip=0, y_flip=0)
        self.bank_insts = [self.right_bank_inst]
        if self.num_banks == 1:
            self.add_right_col_decoder()
        self.add_row_decoder()
        self.add_power_rails()
        if self.num_banks == 2:
            self.add_left_col_decoder()
            x_offset = self.get_left_bank_x()
            self.left_bank_inst = self.add_bank(1, vector(x_offset, 0), x_flip=0, y_flip=-1)
            self.bank_insts = [self.right_bank_inst, self.left_bank_inst]

    def route_layout(self):
        debug.info(1, "Route sram")
        self.route_column_decoder()
        self.route_row_decoder_clk()
        self.join_decoder_wells()
        self.route_decoder_power()
        self.route_decoder_outputs()
        self.join_bank_controls()

        self.join_bank_power_grid()
        self.copy_layout_pins()

    def create_bank(self):
        self.bank = CmosBank(name="bank", word_size=self.word_size, num_words=self.num_words_per_bank,
                             words_per_row=self.words_per_row, num_banks=self.num_banks)
        self.add_mod(self.bank)

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
        assert self.words_per_row <= 8, "Maximum of 8 words per row supported"
        self.create_column_decoder_modules()
        col_decoder_clk = "clk_buf_1" if self.num_banks == 1 else "clk_buf_2"
        if self.words_per_row == 2:
            column_decoder = self.column_decoder
            column_decoder.pins = ["din", "clk", "dout", "dout_bar", "vdd", "gnd"]
            column_decoder.copy_layout_pin(column_decoder.buffer_inst, "out_inv", "dout_bar")
            self.col_decoder_connections = ["ADDR[{}]".format(self.bank_addr_size - 1), col_decoder_clk,
                                            "sel[1]", "sel[0]", "vdd", "gnd"]
        else:
            self.col_decoder_connections = []
            for i in reversed(range(self.col_addr_size)):
                self.col_decoder_connections.append("ADDR[{}]".format(self.bank_addr_size - 1 - i))
            for i in range(self.words_per_row):
                self.col_decoder_connections.append("sel[{}]".format(i))
            self.col_decoder_connections.extend([col_decoder_clk, "vdd", "gnd"])

        self.add_mod(self.column_decoder)

    def add_pins(self):
        for j in range(self.num_banks):
            for i in range(self.word_size):
                self.add_pin("DATA_{0}[{1}]".format(j + 1, i))
                self.add_pin("MASK_{0}[{1}]".format(j + 1, i))
        for i in range(self.bank_addr_size):
            self.add_pin("ADDR[{0}]".format(i))
        bank_sel_2 = ["bank_sel_2"] * int(self.num_banks == 2)
        for pin in ["read", "clk", "bank_sel"] + bank_sel_2 + ["sense_trig", "vdd", "gnd"]:
            self.add_pin(pin)

    def copy_layout_pins(self):
        for bank_inst in self.bank_insts:
            self.copy_layout_pin(bank_inst, "vdd")
            self.copy_layout_pin(bank_inst, "gnd")
        right_bank = self.bank_insts[0]
        for pin_name in ["clk", "sense_trig", "read", "bank_sel"]:
            self.copy_layout_pin(right_bank, pin_name)
        if not self.single_bank:
            self.copy_layout_pin(self.bank_insts[1], "bank_sel", "bank_sel_2")
        for i in range(self.row_addr_size):
            self.copy_layout_pin(self.row_decoder_inst, "A[{}]".format(i), "ADDR[{}]".format(i))
        for j in range(self.num_banks):
            for i in range(self.word_size):
                for pin_name in ["DATA", "MASK"]:
                    self.copy_layout_pin(self.bank_insts[j], pin_name + "[{}]".format(i),
                                         "{0}_{1}[{2}]".format(pin_name, j + 1, i))

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

    def add_right_col_decoder(self):
        if self.words_per_row < 2:
            return

        decoder_y_offset = self.get_col_decoder_y()

        # given the y_offset, find the minimum x offset such that decoder doesn't clash with bank's control rails
        max_x_offset = self.bank.width
        for i in range(len(self.bank.rail_names)):
            rail_name = self.bank.rail_names[i] + "_rail"
            rail = getattr(self.bank, rail_name)
            if rail.uy() > decoder_y_offset:
                max_x_offset = min(max_x_offset, rail.offset.x)

        rails_x_offset = (max_x_offset - (self.words_per_row - 1) * self.m2_pitch)
        decoder_x_offset = rails_x_offset - self.get_wide_space(METAL2) - self.column_decoder.width

        mirror = "MX" if self.words_per_row > 2 else "R0"
        self.column_decoder_inst = self.add_inst("col_decoder", mod=self.column_decoder,
                                                 offset=vector(decoder_x_offset, decoder_y_offset),
                                                 mirror=mirror)
        self.connect_inst(self.col_decoder_connections)

    def add_left_col_decoder(self):
        if self.words_per_row < 2:
            return
        decoder_y = self.get_col_decoder_y()
        decoder_x = self.mid_gnd.lx() - self.wide_space
        if self.words_per_row == 2:
            decoder_x -= 2 * self.m2_pitch
        else:
            decoder_x -= (2 * self.wide_space + self.rail_height)

        mirror = "XY" if self.words_per_row > 2 else "MY"

        self.column_decoder_inst = self.add_inst("col_decoder", mod=self.column_decoder,
                                                 offset=vector(decoder_x, decoder_y), mirror=mirror)
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

        wordline_driver_x = self.bank.wordline_driver_inst.lx()
        left_most_rail_x = self.bank.leftmost_rail.offset.x

        if self.column_decoder_inst is not None:
            if self.words_per_row == 2:
                # leave room for ADDR pin
                max_x_offset = self.column_decoder_inst.lx() - self.wide_space - self.m2_pitch
            else:
                # leave room for vdd and gnd pins to the left
                vdd_pins = self.row_decoder.get_pins("vdd")
                vdd_below_bitcells = list(filter(lambda x: x.by() < self.row_decoder.predecoder_height,
                                                 vdd_pins))
                vdd_extension = max(vdd_below_bitcells, key=lambda x: x.rx()).rx() - self.row_decoder.width
                max_x_offset = (self.column_decoder_inst.lx() - vdd_extension -
                                2 * self.wide_space - self.rail_height)
        else:
            max_x_offset = left_most_rail_x - self.wide_space

        # avoid clash with control_flops
        if self.bank.height - self.row_decoder.height - self.wide_space < self.bank.read_buf_inst.uy():
            max_x_offset = min(max_x_offset, self.bank.get_pin("read").lx() - self.m2_pitch - self.wide_space)

        x_offset = min(wordline_driver_x - self.row_decoder.row_decoder_width,
                       max_x_offset - self.row_decoder.width)
        y_offset = self.bank.wordline_driver_inst.by() - self.row_decoder.predecoder_height

        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.row_decoder,
                                              offset=vector(x_offset, y_offset))

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
            connections.append("MASK_{0}[{1}]".format(bank_num + 1, i))

        if self.words_per_row > 1:
            for i in range(self.words_per_row):
                connections.append("sel[{}]".format(i))
        for i in range(self.num_rows):
            connections.append("dec_out[{}]".format(i))

        bank_sel = "bank_sel" if bank_num == 0 else "bank_sel_2"
        connections.extend([bank_sel, "read", "clk", "sense_trig",
                            "clk_buf_{}".format(bank_num + 1), "clk_bar_{}".format(bank_num + 1),
                            "vdd", "gnd"])
        return connections

    def route_row_decoder_clk(self):
        clk_rail = self.bank.clk_buf_rail
        mask_flop_clk_in = self.bank.mask_in_flops_inst.get_pin("clk")

        if self.column_decoder_inst is None:
            via_y = mask_flop_clk_in.uy()
        else:
            via_y = min(mask_flop_clk_in.uy(), self.column_decoder_inst.by()) - m2m3.height
        decoder_clk_pins = self.row_decoder_inst.get_pins("clk")
        valid_decoder_pins = list(filter(lambda x: x.uy() > via_y, decoder_clk_pins))
        closest_clk = min(valid_decoder_pins, key=lambda x: min(abs(via_y - x.by()), abs(via_y - x.uy())))

        self.add_contact(m2m3.layer_stack, offset=vector(clk_rail.offset.x, via_y))
        self.add_rect(METAL3, offset=vector(closest_clk.lx(), via_y),
                      width=clk_rail.offset.x - closest_clk.lx())

        self.add_contact(m2m3.layer_stack, offset=vector(closest_clk.lx(), via_y))
        if via_y < closest_clk.by():
            self.add_rect("metal2", offset=vector(closest_clk.lx(), via_y), height=closest_clk.by() - via_y)

    def route_column_decoder(self):
        if self.words_per_row < 2:
            return
        if self.words_per_row == 2:
            self.route_flop_column_decoder()
        else:
            self.route_predecoder_column_decoder()

    def route_flop_column_decoder(self):
        # route vdd to wordline driver vdd

        for pin_name in ["vdd", "gnd"]:
            col_decoder_pin = self.column_decoder_inst.get_pin(pin_name)
            row_decoder_pins = self.row_decoder_inst.get_pins(pin_name)

            def filter_pins():
                if pin_name == "vdd":
                    return filter(lambda x: x.by() > col_decoder_pin.by(), row_decoder_pins)
                else:
                    return filter(lambda x: x.uy() < col_decoder_pin.uy(), row_decoder_pins)

            closest_row_pin = min(filter_pins(), key=lambda x: abs(col_decoder_pin.cy() - x.cy()))
            if self.single_bank:
                self.add_rect(METAL1, offset=vector(col_decoder_pin.lx(), col_decoder_pin.by()),
                              width=col_decoder_pin.height(),
                              height=closest_row_pin.by() - col_decoder_pin.by())
                self.add_rect(METAL1, offset=closest_row_pin.lr(), height=closest_row_pin.height(),
                              width=col_decoder_pin.height() + col_decoder_pin.lx() - closest_row_pin.rx())
            else:
                x_offset = col_decoder_pin.rx() - col_decoder_pin.height()
                height = closest_row_pin.cy() - col_decoder_pin.cy()
                if abs(height) > self.m1_width:
                    self.add_rect(METAL1, offset=vector(x_offset, col_decoder_pin.cy()),
                                  width=col_decoder_pin.height(),
                                  height=closest_row_pin.cy() - col_decoder_pin.cy())
                rail = getattr(self, "mid_" + pin_name)
                self.add_rect(METAL1, offset=vector(x_offset, closest_row_pin.by()),
                              height=closest_row_pin.height(), width=rail.rx() - x_offset)
        # clk
        row_decoder_clks = self.row_decoder_inst.get_pins("clk")
        col_decoder_clk = self.column_decoder_inst.get_pin("clk")
        if self.single_bank:
            closest_clk = min(row_decoder_clks, key=lambda x: abs(col_decoder_clk.cy() - x.cy()))
            self.add_contact(m1m2.layer_stack, offset=col_decoder_clk.ll(), rotate=90)
            self.add_rect(METAL2, offset=vector(closest_clk.lx(), col_decoder_clk.by()),
                          width=col_decoder_clk.lx() - closest_clk.lx())
        else:
            # find clk rail
            clk_rail = getattr(self.bank, "clk_buf_rail")
            clk_rail_x = self.bank_insts[1].rx() - (clk_rail.rx())
            mask_in_pin = self.bank.mask_in_flops_inst.get_pin("clk")
            y_offset = mask_in_pin.cy() - 0.5 * m2m3.height
            x_offset = self.column_decoder_inst.rx() + self.wide_space
            self.add_contact(m2m3.layer_stack, offset=vector(clk_rail_x, y_offset))

            self.add_rect(METAL3, offset=vector(clk_rail_x, mask_in_pin.by()), width=x_offset - clk_rail_x)
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, y_offset))
            self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                          height=col_decoder_clk.uy() - y_offset)
            self.add_contact_center(m1m2.layer_stack,
                                    offset=vector(x_offset + 0.5 * self.m1_width, col_decoder_clk.cy()))
            self.add_rect(METAL1, offset=col_decoder_clk.lr(), width=x_offset - col_decoder_clk.rx())
        # address in
        addr_in = self.column_decoder_inst.get_pin("din")
        if self.single_bank:
            x_offset = self.bank.get_pin("read").lx() - self.m2_pitch
            y_bend = self.bank.read_buf_inst.get_pin("gnd").uy() + self.get_parallel_space(METAL2)
            self.add_layout_pin("ADDR[{}]".format(self.addr_size - 1), METAL2,
                                offset=vector(x_offset, self.min_point), height=y_bend - self.min_point)
            self.add_rect(METAL2, offset=vector(x_offset, y_bend), width=addr_in.lx() - x_offset)
            self.add_rect(METAL2, offset=vector(addr_in.lx(), y_bend), height=addr_in.by() - y_bend)
        else:
            self.add_layout_pin("ADDR[{}]".format(self.addr_size - 1), METAL2,
                                offset=vector(addr_in.rx() - self.m2_width, self.min_point),
                                height=addr_in.by() - self.min_point)

        # sel[1]
        sel_1_in = self.bank_insts[self.num_banks - 1].get_pin("sel[1]")
        sel_1_out = self.column_decoder_inst.get_pin("dout")
        x_offset = sel_1_in.lx() if self.single_bank else sel_1_in.rx()
        self.add_rect(METAL1, offset=vector(sel_1_out.rx(), sel_1_in.by()),
                      width=x_offset - sel_1_out.rx())

        # sel[0]
        sel_0_in = self.bank_insts[self.num_banks - 1].get_pin("sel[0]")
        sel_0_out = self.column_decoder_inst.get_pin("dout_bar")
        y_bend = self.column_decoder_inst.uy() + self.wide_space
        if self.single_bank:
            x_bend = self.bank.mid_vdd.lx() - self.wide_space - self.m1_pitch
            x_end = sel_0_in.lx()
        else:
            x_bend = self.column_decoder_inst.lx() - self.wide_space - 2 * self.m2_pitch
            x_end = sel_0_in.rx()
        self.add_rect(METAL2, offset=sel_0_out.ul(), height=y_bend - sel_0_out.uy())
        self.add_contact(m1m2.layer_stack, offset=vector(sel_0_out.lx() + m1m2.height, y_bend),
                         rotate=90)
        self.add_rect(METAL1, offset=vector(sel_0_out.lx(), y_bend), width=x_bend - sel_0_out.lx())
        self.add_contact_center(m1m2.layer_stack, offset=vector(x_bend + 0.5 * m1m2.width,
                                                                y_bend + 0.5 * self.m1_width))
        self.add_rect(METAL2, offset=vector(x_bend, sel_0_in.by()), height=y_bend - sel_0_in.by())
        self.add_contact(m1m2.layer_stack, offset=vector(x_bend, sel_0_in.by()))
        self.add_rect(METAL1, offset=vector(x_bend, sel_0_in.by()), width=x_end - x_bend)

        if not self.single_bank:
            offsets = [x_bend, x_bend - self.m2_pitch]
            self.add_contact(m1m2.layer_stack, offset=vector(offsets[1] + self.m2_width, sel_1_in.by()),
                             rotate=90)
            self.route_right_bank_sel_in(offsets)

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

    def join_decoder_wells(self):
        layers = ["nwell", "pimplant"]
        purposes = ["drawing", "drawing"]

        decoder_inverter = self.row_decoder.inv_inst[-1].mod
        driver_nand = self.bank.wordline_driver.logic_buffer.logic_mod
        decoder_nand = self.row_decoder.nand_inst[0].mod
        decoder_nand_x = self.row_decoder.nand_inst[0].lx() + self.row_decoder_inst.lx()

        row_decoder_right = self.row_decoder_inst.lx() + self.row_decoder.row_decoder_width
        x_shift = self.bank.wordline_driver.buffer_insts[-1].lx()

        for i in range(2):
            logic_rect = max(driver_nand.get_layer_shapes(layers[i], purposes[i]),
                             key=lambda x: x.height)
            decoder_rect = max(decoder_inverter.get_layer_shapes(layers[i], purposes[i]),
                               key=lambda x: x.height)
            top_most = max([decoder_rect, logic_rect], key=lambda x: x.by())
            fill_height = driver_nand.height - top_most.by()
            # extension of rect past top of cell
            rect_y_extension = top_most.uy() - driver_nand.height
            fill_width = self.bank.wordline_driver_inst.lx() - row_decoder_right + x_shift

            if not self.single_bank:
                driver_nand_x = (self.left_bank_inst.rx() -
                                 self.bank.wordline_driver.buffer_insts[0].lx())
                decoder_nand_rect = max(decoder_nand.get_layer_shapes(layers[i], purposes[i]),
                                        key=lambda x: x.height)
                top_most_left = max([decoder_nand_rect, logic_rect], key=lambda x: x.by())
                fill_height_left = driver_nand.height - top_most_left.by()
                rect_y_extension_left = top_most_left.uy() - driver_nand.height
                fill_width_left = decoder_nand_x - driver_nand_x

            # only add at the vdd pins which is where we have nwells
            for vdd_pin in self.row_decoder_inst.get_pins("vdd"):
                if utils.round_to_grid(vdd_pin.cy()) == utils.round_to_grid(
                        self.bank.wordline_driver_inst.by()):  # bottom row
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - rect_y_extension),
                                  width=fill_width, height=top_most.height)
                    if not self.single_bank and layers[i] == "nwell":
                        self.add_rect(layers[i], offset=vector(driver_nand_x, vdd_pin.cy() - rect_y_extension_left),
                                      width=fill_width_left, height=top_most_left.height)
                elif utils.round_to_grid(vdd_pin.cy()) == utils.round_to_grid(
                        self.bank.wordline_driver_inst.uy()):  # top row
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - fill_height),
                                  width=fill_width, height=fill_height + rect_y_extension)
                    if not self.single_bank and layers[i] == "nwell":
                        self.add_rect(layers[i], offset=vector(driver_nand_x, vdd_pin.cy() - fill_height_left),
                                      width=fill_width_left, height=fill_height_left + rect_y_extension_left)
                elif vdd_pin.cy() > self.bank.wordline_driver_inst.by():  # row decoder
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - fill_height),
                                  width=fill_width, height=2 * fill_height)
                    if not self.single_bank and layers[i] == "nwell":
                        self.add_rect(layers[i], offset=vector(driver_nand_x, vdd_pin.cy() - fill_height_left),
                                      width=fill_width_left, height=2 * fill_height_left)

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

    def route_decoder_outputs(self):
        # place m3 rail to the bank wordline drivers just below the power rail
        buffer_mod = self.bank.wordline_driver.logic_buffer
        vdd_pin = buffer_mod.get_pin("vdd")
        rail_y = vdd_pin.by() - self.m3_pitch

        # find rightmost decoder rail x
        right_most_rail = (self.row_decoder_inst.lx() + max(self.row_decoder.rail_x_offsets)
                           + self.m2_pitch - 0.5 * self.m2_width)
        # find x beside wordline driver enable
        if not self.single_bank:
            wl_en_x = (self.left_bank_inst.rx() - self.bank.wordline_driver_inst.get_pin("en").lx() -
                       self.get_parallel_space(METAL2) - self.fill_width)

        for row in range(self.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            wl_ins = [self.right_bank_inst.get_pin("dec_out[{}]".format(row))]
            if not self.single_bank:
                wl_ins.append(self.left_bank_inst.get_pin("dec_out[{}]".format(row)))
            for i in range(len(wl_ins)):
                wl_in = wl_ins[i]

                self.add_contact(m2m3.layer_stack,
                                 offset=vector(decoder_out.ul() - vector(0, m2m3.second_layer_height)))
                y_offset = self.bank.wordline_driver_inst.by() + row * buffer_mod.height + rail_y
                self.add_rect(METAL3, offset=decoder_out.ul(), height=y_offset - decoder_out.uy())

                wl_x = wl_in.cx() - 0.5 * self.m3_width
                if i == 0:
                    self.add_rect(METAL3, offset=vector(decoder_out.lx(), y_offset),
                                  width=wl_x - decoder_out.lx())
                else:
                    # decoder to leftmost rail
                    x_offset = right_most_rail + 0.5 * self.fill_width
                    self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                                  width=decoder_out.lx() - x_offset)
                    via_offset = vector(x_offset - 0.5 * m2m3.width, y_offset + self.m3_width - m2m3.height)
                    self.add_contact(m1m2.layer_stack, offset=via_offset)
                    self.add_contact(m2m3.layer_stack, offset=via_offset)
                    self.add_rect(METAL2,
                                  offset=vector(right_most_rail,
                                                via_offset.y + 0.5 * m2m3.height - 0.5 * self.fill_height),
                                  width=self.fill_width, height=self.fill_height)
                    # leftmost rail to wl_en_x
                    self.add_rect(METAL1, offset=vector(wl_en_x, via_offset.y),
                                  width=x_offset - wl_en_x)
                    via_offset = vector(wl_en_x - 0.5 * m2m3.width, via_offset.y)
                    self.add_contact(m1m2.layer_stack, offset=via_offset)
                    self.add_contact(m2m3.layer_stack, offset=via_offset)
                    self.add_rect_center(METAL2, offset=vector(wl_en_x, via_offset.y + 0.5 * m2m3.height),
                                         width=self.fill_width, height=self.fill_height)
                    self.add_rect(METAL3, offset=vector(wl_x, y_offset), width=via_offset.x - wl_x)

                self.add_rect(METAL3, offset=vector(wl_x, wl_in.cy()),
                              height=y_offset + self.m3_width - wl_in.cy())
                self.add_contact_center(m2m3.layer_stack, wl_in.center())
                self.add_contact_center(m1m2.layer_stack, wl_in.center())

                self.add_rect_center("metal2", offset=wl_in.center(), width=self.fill_height,
                                     height=self.fill_width)

    def join_bank_controls(self):
        if self.single_bank:
            return
        pin_names = ["sense_trig", "clk", "read"]
        y_offset = self.min_point
        for i in range(len(pin_names)):
            left_pin = self.bank_insts[1].get_pin(pin_names[i])
            right_pin = self.bank_insts[0].get_pin(pin_names[i])
            for pin in [left_pin, right_pin]:
                self.add_contact(m2m3.layer_stack, offset=vector(pin.lx(), y_offset))
            self.add_rect(METAL3, offset=vector(left_pin.lx(), y_offset),
                          width=right_pin.lx() - left_pin.lx())
            y_offset += self.m3_pitch

    def join_bank_power_grid(self):
        if not hasattr(self.bank, "gnd_grid_rects"):
            return
        pairs = [(self.mid_gnd, self.bank.gnd_grid_rects), (self.mid_vdd, self.bank.vdd_grid_rects)]
        if self.single_bank:
            cross_rail_x = self.row_decoder_inst.lx()
        else:
            cross_rail_x = self.left_bank_inst.lx()
        for power_rail, grid_rects in pairs:
            for grid_rect in grid_rects:
                self.add_inst(self.bank.m2mtop.name, self.bank.m2mtop,
                              offset=vector(power_rail.lx() + 0.5 * power_rail.width, grid_rect.by()))
                self.connect_inst([])

                self.add_rect(self.bank.bottom_power_layer, offset=vector(cross_rail_x, grid_rect.by()),
                              height=grid_rect.height, width=self.right_bank_inst.rx() - cross_rail_x)

    def add_lvs_correspondence_points(self):
        pass

    def add_cross_contact_center(self, cont, offset, rotate=False,
                                 rail_width=None):
        super().add_cross_contact_center(cont, offset, rotate)
        self.add_cross_contact_center_fill(cont, offset, rotate, rail_width)
