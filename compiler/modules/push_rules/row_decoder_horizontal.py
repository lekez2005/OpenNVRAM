import re

from base import well_implant_fills, utils
from base.contact import m2m3, cross_m2m3, m1m2
from base.design import METAL1, PO_DUMMY, METAL3, METAL2
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.hierarchical_decoder import hierarchical_decoder
from modules.push_rules.predecode2x4_horizontal import predecode2x4_horizontal
from modules.push_rules.predecode3x8_horizontal import predecode3x8_horizontal
from modules.push_rules.push_bitcell_array import push_bitcell_array


class row_decoder_horizontal(hierarchical_decoder):
    rotation_for_drc = GDS_ROT_270
    and_insts = []
    tap_insts = []

    def get_pre2x4_mod(self, num):
        if num == 0:
            return self.pre2_4_neg
        return self.pre2_4

    def get_pre3x8_mod(self, num):
        if num == 0 and self.no_of_pre2x4 == 0:
            return self.pre3_8_neg
        return self.pre3_8

    def add_pins(self):
        super().add_pins()
        self.add_pin("en")

    def create_modules(self):
        self.pre2_4_neg = predecode2x4_horizontal(use_flops=self.use_flops, negate=True)
        self.add_mod(self.pre2_4_neg)
        self.pre2_4 = predecode2x4_horizontal(use_flops=self.use_flops, negate=False)
        self.add_mod(self.pre2_4)

        self.pre3_8_neg = predecode3x8_horizontal(use_flops=self.use_flops, negate=True)
        self.add_mod(self.pre3_8_neg)
        self.pre3_8 = predecode3x8_horizontal(use_flops=self.use_flops, negate=False)
        self.add_mod(self.pre3_8)

        if self.num_inputs in [4, 5]:
            self.decoder_and = self.create_mod_from_str(OPTS.decoder_and_2, rotation=GDS_ROT_270)
            self.decoder_and_tap = self.create_mod_from_str(OPTS.decoder_and_2_tap,
                                                            rotation=GDS_ROT_270)
        else:
            self.decoder_and = self.create_mod_from_str(OPTS.decoder_and_3,
                                                        rotation=GDS_ROT_270)
            self.decoder_and_tap = self.create_mod_from_str(OPTS.decoder_and_3_tap,
                                                            rotation=GDS_ROT_270)

    def calculate_dimensions(self):
        self.nand2 = self.nand3 = self.inv = self.decoder_and
        super().calculate_dimensions()

        self.bitcell_offsets, self.tap_offsets, _ = push_bitcell_array. \
            get_bitcell_offsets(self.rows, 2)

        self.row_decoder_width = self.decoder_and.width + self.routing_width
        self.row_decoder_height = self.bitcell_offsets[-1] + 2 * push_bitcell_array.bitcell.height

        vdd_pin = (self.pre2_4 or self.pre3_8).get_pins("vdd")[0]
        self.predecoder_space = vdd_pin.height() + self.get_wide_space(METAL1)

        self.height = self.predecoder_height + self.row_decoder_height + self.predecoder_space
        self.width = max(self.row_decoder_width, self.predecoder_width + self.routing_width)

        self.nand2 = self.nand3 = self.inv = None

    def add_decoder_inv_array(self):
        pass

    def add_nand_array(self, nand_mod, correct=0):
        """Add and2/and3 instances and taps"""
        self.and_insts = []
        y_base = self.predecoder_height + self.predecoder_space + self.bitcell_height

        for i in range(self.rows):
            if i % 2 == 0:
                offset = vector(self.routing_width, y_base + self.bitcell_offsets[i])
                and_inst = self.add_inst("and_{}".format(i), self.decoder_and, offset=offset)
                self.and_insts.append(and_inst)

    def connect_inst(self, args, check=True):
        """Correct connections for decoder nands"""
        if args and args[0].startswith("out["):  # decoder
            args_str = ' '.join(args)
            row = int(re.search(r"Z\[([0-9]+)\]", args_str).group(1))
            if row % 2 == 1:
                return
            a_conn = int(re.search(r"out\[([0-9]+)\]", args[0]).group(1))
            a_args = ["out[{}]".format(a_conn), "out[{}]".format(a_conn + 1)]
            if len(args) == 5:
                other_inputs = args[1:2]
            else:
                other_inputs = args[1:3]
            other_args = ["en", "gnd", "vdd", "decode[{}]".format(row),
                          "decode[{}]".format(row + 1)]
            args = a_args + other_inputs + other_args

        super().connect_inst(args, check)

    def add_body_contacts(self):
        # additional bitcell because of dummy bitcell
        self.tap_insts = []
        y_base = self.predecoder_height + self.predecoder_space + push_bitcell_array.bitcell.height
        for y_offset in self.tap_offsets:
            tap_inst = self.add_inst(self.decoder_and_tap.name, self.decoder_and_tap,
                                     offset=vector(self.routing_width, y_base + y_offset))
            self.tap_insts.append(tap_inst)
            self.connect_inst([])
        well_implant_fills.fill_horizontal_poly(self, self.and_insts[0],
                                                well_implant_fills.BOTTOM)
        well_implant_fills.fill_horizontal_poly(self, self.and_insts[-1],
                                                well_implant_fills.TOP)
        # fill between all predecoders
        all_predecoders = (self.pre2x4_inst + self.pre3x8_inst)[:-1]
        for bottom_inst in all_predecoders:
            # bottom_inst = self.pre2x4_inst[-1]
            inverter_inst = bottom_inst.mod.inv_inst[-1]
            logic_mod_inst = bottom_inst.mod.nand_inst[-1]
            x_shift = bottom_inst.rx() - 0.5 * (inverter_inst.lx() + logic_mod_inst.rx())
            x_offset = x_shift - self.poly_vert_space
            self.add_rect(PO_DUMMY, offset=vector(x_offset, bottom_inst.uy() - 0.5 * self.poly_width),
                          width=2 * self.poly_vert_space, height=self.poly_width)

    def route_decoder(self):
        for i in range(0, int(self.rows / 2)):
            and_inst = self.and_insts[i]
            row = i * 2
            self.copy_layout_pin(and_inst, "wl<0>", "decode[{}]".format(row))
            self.copy_layout_pin(and_inst, "wl<1>", "decode[{}]".format(row + 1))

        en_pin = self.and_insts[0].get_pin("en")
        pin_height = en_pin.width()

        y_offset = en_pin.by() - self.get_wide_space(METAL3) - pin_height
        self.add_rect(METAL2, offset=vector(en_pin.lx(), y_offset), width=en_pin.width(),
                      height=en_pin.by() - y_offset)
        self.add_layout_pin("en", METAL3, offset=vector(en_pin.lx(), y_offset),
                            height=pin_height, width=self.width - en_pin.lx())
        x_offset = en_pin.lx() + 0.5 * (m2m3.height - self.m3_width)
        y_offset = y_offset
        self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(x_offset, y_offset))
        self.connect_inst([])

    def connect_rails_to_decoder(self):
        row_index = 0

        predec_2 = self.predec_groups[2] if len(self.predec_groups) == 3 else [1]

        for index_C in predec_2:
            for index_B in self.predec_groups[1]:
                for index_A in self.predec_groups[0][::2]:
                    self.connect_rail_m2(index_A, self.and_insts[row_index].get_pin("a_bar<0>"))
                    self.connect_rail_m2(index_A + 1, self.and_insts[row_index].get_pin("a_bar<1>"))

                    self.connect_rail_m2(index_B, self.and_insts[row_index].get_pin("B"))
                    if len(self.predec_groups) == 3:
                        self.connect_rail_m2(index_C, self.and_insts[row_index].get_pin("C"))
                    row_index = row_index + 1

    def connect_rail_m2(self, rail_index, pin):
        rail_offset = vector(self.rail_x_offsets[rail_index], pin.cy())
        via_x = rail_offset.x - 0.5 * self.m2_width
        via_y = pin.cy() - 0.5 * cross_m2m3.height
        self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(via_x, via_y))
        self.connect_inst([])

        self.add_rect(METAL3, offset=vector(rail_offset.x, rail_offset.y - 0.5 * self.m3_width),
                      width=pin.lx() - rail_offset.x)

    def route_vdd_gnd(self):
        # ground pin below en pin
        en_pin = self.get_pin("en")
        gnd_pins = self.and_insts[0].get_pins("gnd")
        pin_height = max(map(lambda x: x.width(), gnd_pins))
        pin_x = min(map(lambda x: x.lx(), gnd_pins))

        y_offset = en_pin.by() - self.get_wide_space(METAL3) - pin_height
        self.add_layout_pin("gnd", METAL3, offset=vector(pin_x, y_offset),
                            height=pin_height, width=self.width - pin_x)
        # AND gates gnd to bottom gnd
        for pin in gnd_pins:
            x_offset = pin.lx() + 0.5 * (m2m3.height - self.m3_width)
            y_offset = y_offset
            self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(x_offset, y_offset))
            self.connect_inst([])
            self.add_rect(METAL2, offset=vector(pin.lx(), y_offset), width=pin.width(),
                          height=pin.by() - y_offset)
        # AND gates vdd to predecoder vdd
        all_predecoders = self.pre2x4_inst + self.pre3x8_inst
        top_predecoder = max(all_predecoders, key=lambda x: x.uy())

        predecoder_vdd = max(top_predecoder.get_pins("vdd"), key=lambda x: x.uy())
        # extend top predecoder vdd
        self.add_layout_pin("vdd", predecoder_vdd.layer, offset=predecoder_vdd.ll(),
                            height=predecoder_vdd.height(), width=self.width - predecoder_vdd.lx())

        y_offset = predecoder_vdd.cy() - 0.5 * m1m2.height
        for pin in self.and_insts[0].get_pins("vdd"):
            self.add_rect(METAL2, offset=vector(pin.lx(), y_offset), width=pin.width(),
                          height=pin.by() - y_offset)
            self.add_contact_center(m1m2.layer_stack, offset=vector(pin.cx(),
                                                                    y_offset + 0.5 * m1m2.height))

        # predecoder vdd and gnd

        for predecoder in all_predecoders:
            for pin_name in ["vdd", "gnd"]:
                self.copy_layout_pin(predecoder, pin_name)
        # tap vdd and gnd
        for tap_inst in self.tap_insts:
            for pin_name in ["vdd", "gnd"]:
                pins = utils.get_libcell_pins([pin_name],
                                              self.decoder_and_tap.child_mod.lib_name)[pin_name]
                setattr(self, "tap_{}_pins".format(pin_name), pins)
                for pin in pins:
                    x_offset = tap_inst.lx() + pin.by()
                    y_offset = tap_inst.by() + (tap_inst.height - pin.rx())
                    self.add_layout_pin(pin_name, pin.layer,
                                        offset=vector(x_offset, y_offset),
                                        height=pin.width(),
                                        width=self.width - x_offset)
