from base.contact import cross_m1m2
from base.design import METAL1, PIMP, NIMP
from base.geometry import NO_MIRROR, MIRROR_X_AXIS
from base.vector import vector
from modules.hierarchical_decoder import hierarchical_decoder
from modules.hierarchical_predecode2x4 import hierarchical_predecode2x4
from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8
from modules.horizontal.pinv_wordline import pinv_wordline
from modules.horizontal.pnand2_wordline import pnand2_wordline, pnand3_wordline
from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap
from tech import drc


class row_decoder_horizontal(hierarchical_decoder):

    def create_modules(self):
        self.inv = pinv_wordline(size=2, mirror=True)
        self.add_mod(self.inv)

        self.nand2 = pnand2_wordline(mirror=False)
        self.add_mod(self.nand2)

        self.nand3 = pnand3_wordline(mirror=False)
        self.add_mod(self.nand3)

        self.create_predecoders()

        self.pwell_tap = wordline_pgate_tap(self.inv, PIMP)
        self.nwell_tap = wordline_pgate_tap(self.inv, NIMP)

    def create_predecoders(self):
        super().create_predecoders()
        if self.no_of_pre3x8 == 0:
            self.top_predecoder = hierarchical_predecode2x4(route_top_rail=True, use_flops=self.use_flops)
        else:
            self.top_predecoder = hierarchical_predecode3x8(route_top_rail=True, use_flops=self.use_flops)
        self.add_mod(self.top_predecoder)

    def get_pre2x4_mod(self, num):
        if num == (self.no_of_pre2x4 + self.no_of_pre3x8) - 1:
            return self.top_predecoder
        return self.pre2_4

    def get_pre3x8_mod(self, num):
        if num == self.no_of_pre3x8 - 1:
            return self.top_predecoder
        return self.pre3_8

    def get_row_y_offset(self, row):
        y_offset = self.bitcell_offsets[row]
        if row % 2 == 0:
            mirror = MIRROR_X_AXIS
            y_offset += self.inv.height
        else:
            mirror = NO_MIRROR

        y_off = self.predecoder_height + y_offset
        return y_off, mirror

    def calculate_dimensions(self):
        super().calculate_dimensions()
        if self.bitcell_offsets[0] > 0:
            extra_height = self.bitcell_offsets[0]
        else:
            extra_height = drc["pwell_to_nwell"] + 2 * self.well_enclose_active

        self.predecoder_height += extra_height
        self.height += extra_height

    def connect_rail_m2(self, rail_index, pin):
        x_offset = self.rail_x_offsets[rail_index]
        self.add_cross_contact_center(cross_m1m2, offset=vector(x_offset, pin.cy()), rotate=True)
        self.add_rect(METAL1, offset=vector(x_offset, pin.cy() - 0.5 * self.m1_width),
                      width=pin.lx() - x_offset)

    def join_nand_inv_pins(self, z_pin, a_pin):
        self.add_path(METAL1, [z_pin.rc() - vector(0.5 * self.m1_width, 0), a_pin.lc()])

    def fill_predecoder_to_row_decoder_implants(self):
        pass

    def add_body_contacts(self):
        self.tap_insts = []
        module_insts = [self.nand_inst[0], self.inv_inst[0]]
        for y_offset in self.tap_offsets:
            tap_insts = wordline_pgate_tap.add_buffer_taps(self, 0, y_offset + self.predecoder_height,
                                                           module_insts,
                                                           self.pwell_tap, self.nwell_tap)
            self.tap_insts.extend(tap_insts)
