import debug
from base.contact import m2m3, cross_m2m3, m3m4
from base.design import METAL3, design, METAL2, METAL4
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import EXACT
from modules.baseline_sram import BaselineSram
from modules.bitline_compute.bitline_alu import BitlineALU
from modules.bitline_compute.bl_bank import BlBank


class BlSram(BaselineSram):
    bank = None  # type: BlBank
    bank_inst = None

    alu = alu_inst = None

    alu_num_words = 1

    def compute_sizes(self, word_size, num_words, num_banks, words_per_row):
        super().compute_sizes(word_size, num_words, num_banks, words_per_row)
        self.alu_num_words = int(self.num_cols / OPTS.alu_word_size)

    def create_modules(self):
        super().create_modules()

        self.create_alu()

        self.wordline_driver_inst_real, self.bank.wordline_driver_inst = (
            self.bank.wordline_driver_inst, self.bank.decoder_logic_inst)

    def create_alu(self):
        self.alu = BitlineALU(bank=self.bank, num_cols=self.num_cols, word_size=OPTS.alu_word_size,
                              cells_per_group=OPTS.alu_cells_per_group,
                              inverter_size=OPTS.alu_inverter_size)
        self.add_mod(self.alu)

    def add_modules(self):
        y_offset = - self.alu.bank_y_shift
        self.alu_inst = self.add_inst("alu", mod=self.alu, offset=vector(0, y_offset))

        self.connect_inst(self.get_alu_connections())

        self.bank_inst = self.add_inst("bank0", mod=self.bank, offset=vector(0, 0))
        self.right_bank_inst = self.bank_inst
        self.bank_insts = [self.bank_inst]

        connections = self.get_bank_connections(0, self.bank)
        self.connect_inst(connections)

        self.add_row_decoder()
        self.add_power_rails()

    def route_layout(self):
        self.route_bitline_compute_pins()
        super().route_layout()

    def get_schematic_pin_insts(self):
        return [self.bank_inst, self.right_decoder_inst, self.left_decoder_inst,
                self.column_decoder_inst, self.alu_inst]

    def get_alu_connections(self):
        connections = self.bank.connections_from_mod(self.alu, [
            ("data_in[", "DATA["), ("mask_in[", "MASK["),
            ("and_in[", "and["), ("nor_in[", "nor["),
            ("bus_out[", "bus["), ("mask_bar_out[", "mask_bar["),
            ("sr_clk", "clk", EXACT),
            ("latch_clk", "clk_buf", EXACT),
            ("s_data_in", "s_data")
        ])
        return connections

    def get_bank_connections(self, bank_num, bank_mod):
        replacements = super().get_bank_connection_replacements()
        replacements.extend([
            ("DATA[", "bus["),
            ("mask_in_bar[", "mask_bar["),
            ("vref", "sense_amp_ref")
        ])
        if self.bank.mirror_sense_amp:
            replacements.remove(("clk_buf", "decoder_clk"))

        return bank_mod.connections_from_mod(bank_mod, replacements)

    def add_row_decoder(self):
        super().add_row_decoder()
        self.row_decoder_inst.name = "row_decoder_1"
        x_offset = self.row_decoder_inst.lx() - self.row_decoder.width - self.bus_space
        self.row_decoder_inst_0 = self.add_inst("row_decoder", self.row_decoder,
                                                offset=vector(x_offset, self.row_decoder_inst.by()))
        self.left_decoder_inst, self.right_decoder_inst = (self.row_decoder_inst_0,
                                                           self.row_decoder_inst)
        self.connect_inst(self.get_row_decoder_0_connections())

    def get_row_decoder_connections(self):
        connections = self.bank.connections_from_mod(self.bank.decoder, [
            ("A[", "ADDR_1["), ("clk", "decoder_clk", EXACT),
            ("decode[", "dec_in_1[")
        ])
        return connections

    def get_row_decoder_0_connections(self):
        connections = self.bank.connections_from_mod(self.bank.decoder, [
            ("A[", "ADDR["), ("clk", "decoder_clk", EXACT),
            ("decode[", "dec_in_0[")
        ])
        return connections

    @staticmethod
    def get_bitline_compute_pin_map():
        return [(("and", "and_in"), ("nor", "nor_in")),
                (("DATA", "bus_out"), ("mask_in_bar", "mask_bar_out"))]

    def route_bitline_compute_pins(self):
        pin_pairs = self.get_bitline_compute_pin_map()
        pitch = self.get_parallel_space(METAL4) + m3m4.height
        line_end_space = self.get_line_end_space(METAL4)
        y_offset = self.bank_inst.get_pin("and[0]").by() - pitch
        y_offsets = [y_offset, y_offset - line_end_space - self.m4_width]
        y_offsets.append(y_offsets[1] - line_end_space - m3m4.height)

        via_ext = self.get_drc_by_layer(METAL3, "wide_metal_via_extension") or 0.0
        for col in range(self.num_cols):
            for i in [0, 1]:
                for j, (bank_name, alu_name) in enumerate(pin_pairs[i]):
                    bank_pin = self.bank_inst.get_pin(f"{bank_name}[{col}]")
                    alu_pin = self.alu_inst.get_pin(f"{alu_name}[{col}]")

                    if i == 0:
                        self.add_rect(METAL4, alu_pin.ul(), width=alu_pin.width(),
                                      height=y_offsets[1] + self.m4_width - alu_pin.uy())
                        self.add_rect(METAL4, vector(alu_pin.lx(), y_offsets[1]),
                                      width=bank_pin.cx() - alu_pin.lx())
                        self.add_rect(METAL4, vector(bank_pin.lx(), y_offsets[1]),
                                      height=bank_pin.by() - y_offsets[1], width=bank_pin.width())
                    else:

                        if j == 0:
                            via_x = alu_pin.cx() - m3m4.width
                            m3_edge = bank_pin.cx() - 0.5 * m3m4.width - via_ext
                        else:
                            via_x = alu_pin.cx()
                            m3_edge = bank_pin.cx() + 0.5 * m3m4.width + via_ext

                        for y_offset, pin, pin_edge in [(y_offsets[0], bank_pin, bank_pin.by()),
                                                        (y_offsets[2] + m3m4.height,
                                                         alu_pin, alu_pin.uy())]:
                            self.add_rect(METAL4, vector(pin.lx(), pin_edge), width=pin.width(),
                                          height=y_offset - pin_edge)
                        self.add_contact(m3m4.layer_stack,
                                         vector(bank_pin.cx() - 0.5 * m3m4.width, y_offsets[0]))
                        self.add_contact(m3m4.layer_stack, vector(via_x, y_offsets[2]))

                        self.add_rect(METAL3, vector(m3_edge, y_offsets[0]), height=m3m4.height,
                                      width=via_x - m3_edge)
                        self.add_rect(METAL3, vector(via_x, y_offsets[2]),
                                      width=self.m3_width,
                                      height=y_offsets[0] + m3m4.height - y_offsets[2])

    def route_row_decoder_clk(self, min_clk_rail_y=None):
        min_clk_rail_y = (self.bank.decoder_enable_rail.by() + self.bus_pitch +
                          self.bank_inst.by())
        super().route_row_decoder_clk(min_clk_rail_y=min_clk_rail_y)
        decoder_clk_pins = self.row_decoder_inst.get_pins("clk")
        lowest_pin = min(decoder_clk_pins, key=lambda x: x.by())
        y_offset = (lowest_pin.uy() - 0.5 * self.rail_height -
                    self.get_wide_space(METAL3) - 0.5 * m2m3.height)
        design.add_cross_contact_center(self, cross_m2m3, vector(lowest_pin.cx(), y_offset))

        left_pin = min(self.row_decoder_inst_0.get_pins("clk"),
                       key=lambda x: abs(x.cy() - lowest_pin.cy()))
        extension = 0.5 * cross_m2m3.width
        self.add_rect(METAL3, offset=vector(left_pin.cx() - extension, y_offset - 0.5 * self.bus_width),
                      width=lowest_pin.cx() - left_pin.cx() + 2 * extension,
                      height=self.bus_width)

        design.add_cross_contact_center(self, cross_m2m3, vector(left_pin.cx(), y_offset))

    def route_decoder_power(self):
        left_decoder, self.row_decoder_inst = self.row_decoder_inst, self.row_decoder_inst_0
        super().route_decoder_power()
        self.row_decoder_inst = left_decoder
        # join left and right decoder powers
        right_pin = min(self.right_decoder_inst.get_pins("vdd"), key=lambda x: x.by())
        for pin in (self.left_decoder_inst.get_pins("vdd") +
                    self.left_decoder_inst.get_pins("gnd")):
            self.add_rect(pin.layer, pin.lr(), width=right_pin.lx() - pin.rx(),
                          height=pin.height())

        # bank power to alu power
        bank_power_y = self.bank_inst.by() + self.bank.right_vdd.by()

        for pin_name in ["vdd", "gnd"]:
            for alu_pin in self.alu_inst.get_pins(pin_name):
                if not alu_pin.layer == METAL4:
                    continue
                self.add_rect(METAL4, alu_pin.ul(), width=alu_pin.width(),
                              height=bank_power_y - alu_pin.uy())
                # self.add_rect(METAL2, alu_pin.ul(), width=alu_pin.width(),
                #               height=bank_power_y - alu_pin.uy())
                if pin_name == "vdd":
                    self.m4_vdd_rects.append(alu_pin)
                else:
                    self.m4_gnd_rects.append(alu_pin)

    def add_power_rails(self):
        # decoder power
        min_decoder_x = self.left_decoder_inst.lx()
        if self.column_decoder_inst is not None:
            min_decoder_x = min(min_decoder_x, self.column_decoder_inst.lx() - 2 * self.bus_pitch)
        x_offset = min_decoder_x
        rails = []
        for pin_name in ["vdd", "gnd"]:
            bank_rail = getattr(self.bank, f"mid_{pin_name}")
            x_offset -= self.wide_space + bank_rail.width()
            rails.append(self.add_rect(METAL2, vector(x_offset, 0), width=bank_rail.width(),
                                       height=bank_rail.uy() + self.bank_inst.by()))
        self.mid_vdd, self.mid_gnd = rails

    def route_decoder_outputs(self):
        target_insts = [self.row_decoder_inst_0, self.row_decoder_inst]
        for row in range(self.num_rows):
            for i in range(2):
                bank_in = self.bank_inst.get_pin(f"dec_in_{i}[{row}]")
                dec_out = target_insts[i].get_pin(f"decode[{row}]")
                y_offset = dec_out.uy() if i == 0 else dec_out.by()
                self.add_rect(METAL2, vector(dec_out.lx(), y_offset), width=dec_out.width(),
                              height=bank_in.cy() - y_offset)
                self.add_cross_contact_center(cross_m2m3, vector(dec_out.cx(), bank_in.cy()),
                                              fill=False)
                self.add_rect(METAL3, vector(dec_out.cx(), bank_in.by()),
                              height=bank_in.height(), width=bank_in.lx() - dec_out.cx())

    def copy_layout_pins(self):
        for pin in self.pins:
            if pin in self.pin_map:
                continue
            for inst in [self.bank_inst, self.alu_inst, self.left_decoder_inst,
                         self.right_decoder_inst]:
                conn_index = self.insts.index(inst)
                inst_conns = self.conns[conn_index]
                if pin in inst_conns:
                    pin_index = inst_conns.index(pin)
                    debug.info(2, "Copy inst %s layout pin %s to %s", inst.name,
                               inst.mod.pins[pin_index], pin)
                    self.copy_layout_pin(inst, inst.mod.pins[pin_index], pin)
                    break
            self.copy_layout_pin(self.bank_inst, "clk")

    def copy_bank_pins(self):
        skipped_pins = ["mask_in_bar", "clk_buf", "decoder_clk"]
        for pin_name in self.bank.pins:
            ignored = False
            for skipped_pin in skipped_pins:
                if pin_name.startswith(skipped_pin):
                    ignored = True
                    break

            if not ignored:
                new_pin_name = pin_name
                if pin_name.startswith("DATA"):
                    new_pin_name = pin_name.replace("DATA", "bus")

                self.copy_layout_pin(self.bank_inst, pin_name, new_pin_name)

    def add_lvs_correspondence_points(self):
        pass
