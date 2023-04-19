import re

import debug
from base import utils
from base.contact_full_stack import ContactFullStack
from base.design import METAL4
from base.vector import vector
from modules.bitline_compute.bl_sram import BlSram
from modules.sram_mixins import StackedDecoderMixin
from modules.sram_power_grid import WordlineVddMixin


class Bl1t1sSram(WordlineVddMixin, StackedDecoderMixin, BlSram):
    def compute_sizes(self, word_size, num_words, num_banks, words_per_row):
        assert num_banks == 1, "Only one bank supported"
        assert words_per_row == 1, "Num words per row must be 1"
        assert num_words % 2 == 0, "Even number of words required"
        super().compute_sizes(word_size, int(num_words / 2), num_banks, words_per_row)
        self.col_addr_size = 1
        self.addr_size += 1

    def add_pins(self):
        super().add_pins()

    def create_bank(self):
        self.words_per_row = 1
        super().create_bank()
        self.words_per_row = 2
        self.num_words *= 2

    def add_row_decoder(self):
        super().add_row_decoder()
        self.add_col_decoder()

    def get_wordline_vdd_reference_y(self):
        decoder_logic = self.bank.decoder_logic
        # return self.bank
        return utils.round_to_grid(decoder_logic.in_1_bar_insts[0].by())

    def route_decoder_outputs(self):
        BlSram.route_decoder_outputs(self)

    def route_bitline_compute_pins(self):
        pin_pairs = self.get_bitline_compute_pin_map()
        pin_pairs = pin_pairs[0] + pin_pairs[1]
        sorted_pairs = list(sorted(pin_pairs, key=lambda x: self.
                                   bank_inst.get_pin(f"{x[0]}[0]").lx()))

        pitch = self.get_parallel_space(METAL4) + self.m4_width

        for col in range(self.num_cols):
            for i, (bank_name, alu_name) in enumerate(sorted_pairs):
                bank_pin = self.bank_inst.get_pin(f"{bank_name}[{col}]")
                alu_pin = self.alu_inst.get_pin(f"{alu_name}[{col}]")
                y_offset = alu_pin.uy() + (i + 1) * pitch
                self.add_rect(METAL4, vector(bank_pin.lx(), y_offset), width=bank_pin.width(),
                              height=bank_pin.by() - y_offset)
                self.add_rect(METAL4, alu_pin.ul(), width=alu_pin.width(),
                              height=y_offset + self.m4_width - alu_pin.uy())
                self.add_rect(METAL4, vector(alu_pin.cx(), y_offset), height=self.m4_width,
                              width=bank_pin.cx() - alu_pin.cx())

    @staticmethod
    def shift_address_nets(connections):
        pattern = re.compile(r"^(ADDR.*\[)([0-9]+)(\S+)")
        result = []
        for net in connections:
            matches = pattern.findall(net)
            if matches:
                matches = matches[0]
                result.append(f"{matches[0]}{int(matches[1]) + 1}{matches[2]}")
            else:
                result.append(net)
        debug.info(3, "Shifted nets: %s", ', '.join(result))
        return result

    def get_row_decoder_connections(self):
        return self.shift_address_nets(super().get_row_decoder_connections())

    def get_row_decoder_0_connections(self):
        return self.shift_address_nets(super().get_row_decoder_0_connections())

    def route_decoder_power(self):
        super().route_decoder_power()
        for pin_name in ["vdd", "gnd"]:
            for pin in self.right_decoder_inst.get_pins(pin_name):
                self.add_rect(pin.layer, pin.lr(), height=pin.height(),
                              width=self.bank_inst.lx() - pin.rx())

    def calculate_grid_m4_vias(self, m_top_via):

        self.m6_vdd_pins = [x for x in self.right_bank_inst.get_pins("vdd")
                            if x.layer == "metal6"]
        self.m6_gnd_pins = [x for x in self.right_bank_inst.get_pins("gnd")
                            if x.layer == "metal6"]

        max_width = min(map(lambda x: x.width(), self.m6_vdd_pins + self.m6_gnd_pins))

        self.m6_m7_via = ContactFullStack(start_layer="metal6", stop_layer="metal7",
                                          centralize=True, dimensions=[3, 1])
        self.m7_top_via = ContactFullStack(start_layer="metal7", stop_layer=self.power_grid_y_layer,
                                           centralize=True, max_width=max_width)
        return super().calculate_grid_m4_vias(m_top_via)

    def connect_y_rail_to_m4(self, rail_rect, m4_rects, all_m4_vias, m5_via):
        super().connect_y_rail_to_m4(rail_rect, m4_rects, all_m4_vias, m5_via)

        m6_pins = self.m6_vdd_pins if rail_rect.name == "vdd" else self.m6_gnd_pins
        for pin in m6_pins:
            if pin.by() >= rail_rect.by() or pin.uy() <= rail_rect.uy():
                continue
            offset = vector(pin.cx(), rail_rect.cy() - 0.5 * self.m6_m7_via.height)
            self.add_inst(self.m6_m7_via.name, self.m6_m7_via, offset)
            self.connect_inst([])
            offset = vector(pin.cx(), rail_rect.cy() - 0.5 * self.m7_top_via.height)
            self.add_inst(self.m7_top_via.name, self.m7_top_via, offset)
            self.connect_inst([])
