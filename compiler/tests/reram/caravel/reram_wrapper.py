"""Combine multiple SRAM banks into one"""
import math
import os

import caravel_config
import debug
import tech
from base import utils
from base.contact import cross_m2m3, cross_m3m4, m2m3, m3m4
from base.design import design, METAL5, METAL2, METAL3, METAL4
from base.geometry import MIRROR_Y_AXIS, NO_MIRROR, MIRROR_X_AXIS, MIRROR_XY
from base.hierarchy_layout import layout as hierarchy_layout
from base.hierarchy_spice import spice as hierarchy_spice, INPUT, OUTPUT, INOUT
from base.pin_layout import pin_layout
from base.spice_parser import SpiceParser
from base.utils import pin_rect, round_to_grid as round_
from base.vector import vector
from caravel_config import sram_configs, module_y_space, rail_pitch, rail_width
from globals import OPTS
from pin_assignments_mixin import PinAssignmentsMixin
from router_mixin import METAL6

top_left = sram_configs[0]
top_right = sram_configs[1]
bottom_left = sram_configs[2]
bottom_right = sram_configs[3]


class LoadFromGDS(design):

    def __init__(self, name, gds_file, spice_file=None):
        self.name = name
        self.gds_file = gds_file
        self.sp_file = spice_file

        debug.info(2, "Load %s from %s", self.name, self.gds_file)

        if spice_file is not None:
            hierarchy_spice.__init__(self, self.name)
        hierarchy_layout.__init__(self, self.name)
        self.root_structure = [x for x in self.gds.xyTree if x[0].startswith(self.name)][0]

        (self.width, self.height) = utils.get_libcell_size(gds_file, tech.GDS["unit"],
                                                           tech.layer["boundary"])
        debug.info(2, "Mod %s width = %5.5g height=%5.5g", self.name, self.width, self.height)
        self.pin_map = {}

    def get_pins(self, pin_name):
        pin_name = pin_name.lower()
        if pin_name not in self.pin_map:
            # get pin non-recursively to save time
            pins = []
            gds = self.gds
            label_list = gds.getLabelDBInfo(pin_name, tech.layer_pin_map)
            for label in label_list:
                (label_coordinate, label_layer) = label
                boundaries = gds.getPinInStructure(label_coordinate, label_layer,
                                                   self.root_structure)
                boundary = max(boundaries, key=lambda x: (x[2] - x[0]) * (x[3] - x[1]))
                boundary = [x * self.gds.units[0] for x in boundary]
                rect = pin_rect(boundary)
                pins.append(pin_layout(pin_name, rect, label_layer))

            self.pin_map[pin_name] = pins
        return self.pin_map[pin_name]

    def get_pin(self, text):
        return self.get_pins(text)[0]


class Sram(LoadFromGDS):
    pass


class ReRamWrapper(design):
    def __init__(self):
        design.__init__(self, "sram1")
        debug.info(1, "Creating Sram Wrapper %s", self.name)
        self.create_layout()
        self.add_boundary()
        tech.add_tech_layers(self)
        self.generate_spice()
        self.generate_gds()
        self.generate_verilog()

    def create_layout(self):
        self.pins_to_mid_rails = []
        self.connection_replacements = [{}, {}, {}, {}]
        self.create_srams()
        self.evaluate_pins()
        self.add_srams()
        self.join_bank_pins()
        self.connect_indirect_rail_pins()
        self.add_power_grid()
        self.create_netlist()
        self.verify_connections()

    def create_netlist(self):
        pins = set()
        for i, bank in enumerate(self.bank_insts):
            connections = bank.mod.pins
            conn_index = self.insts.index(bank)
            replacements = self.connection_replacements[i]
            connections = [replacements.get(x, x) for x in connections]

            pins.update([x for x in connections if not x.startswith("data_out_internal")])

            self.conns[conn_index] = connections
            replacements_sort = sorted([(key, value) for key, value in replacements.items()],
                                       key=lambda x: x[0])
            replacement_str = [f"{key} <==> {value}" for key, value in replacements_sort]
            debug.info(2, "Bank %d, connection replacements: %s", i,
                       ", ".join(replacement_str))
        self.pins = list(sorted(pins))

    def verify_connections(self):
        """Ensure all pins have been connected totop level"""
        unconnected_pins = []
        for i, bank in enumerate(self.bank_insts):
            connections = self.conns[self.insts.index(bank)]
            for net in connections:
                if not net.startswith("data_out_internal_") and net not in self.pin_map:
                    unconnected_pins.append((i, net))
        if unconnected_pins:
            debug.error(f"Unconnected bank pins: %s", -1, str(unconnected_pins))

    def create_srams(self):
        debug.info(1, "Loading SRAM sub-bank modules")
        self.sram_mods = {}
        create_count = 0
        for config in sram_configs:
            if config.module_name in self.sram_mods:
                sram = self.sram_mods[config.module_name]
            else:
                sram = LoadFromGDS(config.module_name, config.get_gds_file(), config.spice_file)
                self.sram_mods[config.module_name] = sram
                create_count += 1
                suffix = f"_ram{create_count}"
                if create_count > 1:
                    sram.gds.add_suffix_to_structures(suffix)
                    parser = SpiceParser(config.spice_file)
                    parser.add_module_suffix(suffix=suffix, exclusions=[sram.name])
                    temp_spice = parser.export_spice()
                    sram.spice = []
                    for line in temp_spice:
                        sram.spice.append(line.replace(f"sky130_fd_pr__reram_reram_cell{suffix}",
                                                       "sky130_fd_pr__reram_reram_cell"))

            sram.word_size = config.word_size
            config.sram = sram
            self.add_mod(sram)
            debug.info(1, "Loaded SRAM sub-bank %s", sram.name)

    def evaluate_pins(self):
        if PinAssignmentsMixin.num_address_pins is None:
            from caravel_wrapper import CaravelWrapper
            CaravelWrapper.analyze_sizes()
        num_rails = PinAssignmentsMixin.num_address_pins + len(caravel_config.mid_control_pins)

        def noop(*args):
            pass

        self.num_data_out = 1 + PinAssignmentsMixin.assign_gpio_pins(noop)

        # 2 from data_others, mask_others, 3x since data_in, mask_in, data_out
        num_rails += 3 * self.num_data_out + 2
        # G S G S G for clk, sense_trig
        num_rails += 3
        # bank sels
        num_rails += 4

        self.num_rails = num_rails
        self.y_mid_space = (2 * caravel_config.module_y_space + self.num_rails *
                            caravel_config.rail_pitch - caravel_config.rail_space)

        self.m3_fill_width = m2m3.h_2
        _, self.m3_fill_height = self.calculate_min_area_fill(self.m3_fill_width,
                                                              layer=METAL3)

    def add_srams(self):
        debug.info(1, "Adding SRAM sub-banks")
        self.sram_insts = {}

        def get_vdd(mod, layer):
            return [x for x in mod.get_pins("vdd") if x.layer == layer]

        def align_vdd_y(left_mod, right_mod):
            left_vdd = min(get_vdd(left_mod, METAL5), key=lambda x: x.cy())
            right_vdd = min(get_vdd(right_mod, METAL5), key=lambda x: x.cy())
            return left_vdd.cy() - right_vdd.cy()

        def align_vdd_x(top_mod, bottom_mod):
            top_vdd = min(get_vdd(top_mod, METAL6), key=lambda x: x.cx())
            bot_vdd = min(get_vdd(bottom_mod, METAL6), key=lambda x: x.cx())
            return top_vdd.cx() - bot_vdd.cx()

        # evaluate y offsets
        top_left_y = 0
        top_right_y = align_vdd_y(top_left.sram, top_right.sram)

        bottom_y = min(top_left_y, top_right_y) - self.y_mid_space

        bottom_y_shift = align_vdd_y(bottom_left.sram, bottom_right.sram)
        bottom_left_y = bottom_y
        bottom_right_y = bottom_y - bottom_y_shift

        # evaluate x offsets
        top_left_x = top_left.sram.width
        x_shift = align_vdd_x(top_left.sram, bottom_left.sram)
        bottom_left_x = top_left_x - x_shift

        x_offset = max(bottom_left_x, top_left_x) + caravel_config.module_x_space
        x_shift = align_vdd_x(top_right.sram, bottom_right.sram)

        top_right_x = x_offset
        bottom_right_x = x_offset + x_shift

        def add_inst(name, config, x_offset, y_offset, mirror):
            inst = self.add_inst(name, config.sram, vector(x_offset, y_offset),
                                 mirror=mirror)
            self.connect_inst([], check=False)
            return inst

        self.top_left_inst = add_inst("top_left", top_left, top_left_x,
                                      top_left_y, MIRROR_Y_AXIS)
        self.top_right_inst = add_inst("top_right", top_right, top_right_x,
                                       top_right_y, NO_MIRROR)
        self.bottom_left_inst = add_inst("bottom_left", bottom_left, bottom_left_x,
                                         bottom_left_y, MIRROR_XY)
        self.bottom_right_inst = add_inst("bottom_right", bottom_right, bottom_right_x,
                                          bottom_right_y, MIRROR_X_AXIS)
        self.bank_insts = [self.top_left_inst, self.top_right_inst,
                           self.bottom_left_inst, self.bottom_right_inst]
        self.offset_all_coordinates()
        self.width = max(self.bottom_right_inst.rx(), self.top_right_inst.rx())
        self.height = max(self.top_left_inst.uy(), self.top_right_inst.uy())

        bottom_inst_top = max(self.bottom_left_inst.uy(), self.bottom_right_inst.uy())
        self.mid_rail_y = bottom_inst_top + 0.5 * self.y_mid_space
        self.bottom_mid_via_y = bottom_inst_top + 0.5 * module_y_space

        top_inst_bottom = min(self.top_left_inst.by(), self.top_right_inst.by())
        self.top_mid_via_y = top_inst_bottom - 0.5 * module_y_space

    def get_rail_y(self, y_index):
        return self.mid_rail_y + y_index * rail_pitch

    def connect_indirect_rail_pins(self):

        m2_pin_names = ["clk", "web", "sense_trig", "csb"]
        m2_rails = []

        # make unique
        all_mid_x = []
        rails = []
        for rail in self.pins_to_mid_rails:
            mid_x = utils.round_to_grid(rail[0].cx())
            if rail[0].name in m2_pin_names:
                m2_rails.append(rail)
            if mid_x in all_mid_x:
                continue
            rails.append(rail)
            all_mid_x.append(mid_x)

        pins_to_mid_rails = list(sorted(rails, key=lambda x: x[0].cx()))

        # group by left, right and move m2 pins to the left or right to prevent m4 space
        m2_rails = list(sorted(m2_rails, key=lambda x: x[0].lx()))
        min_space = 1
        m2_groups = [[m2_rails[0]]]
        for m2_rail in m2_rails[1:]:
            if m2_rail[0].lx() - m2_groups[-1][-1][0].lx() < min_space:
                m2_groups[-1].append(m2_rail)
            else:
                m2_groups.append([m2_rail])

        space = m3m4.h_2 + self.m4_space
        for i, group in enumerate(m2_groups):
            base_x = group[0][0].cx()
            if base_x < min(self.top_right_inst.lx(), self.bottom_right_inst.lx()):
                scale = 1
            else:
                scale = -1
                group = list(reversed(group))
            for j, rail in enumerate(group):
                pin = rail[0]
                mid_y = pin.by() - space * (len(group) - 1 - j)
                mid_x = base_x + scale * (j * space)
                self.add_path(METAL2, [vector(pin.cx(), pin.by() + self.m2_width),
                                       vector(pin.cx(), pin.by()),
                                       vector(pin.cx(), mid_y),
                                       vector(mid_x, mid_y)], width=pin.width())
                rect = self.add_rect_center(METAL2, vector(mid_x, mid_y),
                                            width=pin.width(), height=pin.width())
                rect.layer = pin.layer
                rail[0] = rect
                self.add_rect(METAL3, vector(rect.cx(), rail[1] - 0.5 * rail_width),
                              width=pin.cx() - rect.cx(), height=rail_width)

        for index, (pin, y_offset) in enumerate(pins_to_mid_rails):
            if pin.by() > self.mid_rail_y:
                layer = METAL4
                # from pin to intermediate via
                mid_via_y = self.top_mid_via_y - (index % 2) * rail_pitch
                start_y = pin.by()
                height = mid_via_y - start_y - 0.5 * m3m4.h_2
                # intermediate via to middle destination
                dest_rail_width = self.m4_width
                dest_rail_y = mid_via_y + 0.5 * m3m4.h_2
                dest_rail_height = y_offset - 0.5 * m3m4.h_2 - dest_rail_y
            else:
                layer = METAL2
                mid_via_y = self.bottom_mid_via_y + (index % 2) * rail_pitch
                start_y = pin.uy()
                height = mid_via_y - start_y + 0.5 * m2m3.h_1

                dest_rail_width = self.bus_width
                dest_rail_y = mid_via_y - 0.5 * m2m3.h_1
                dest_rail_height = y_offset + 0.5 * m2m3.h_1 - dest_rail_y

            self.add_rect(pin.layer, vector(pin.lx(), start_y), width=pin.rx() - pin.lx(),
                          height=height)
            via_offset = vector(pin.cx(), mid_via_y)
            self.add_cross_contact_center(cross_m2m3, via_offset)
            self.add_cross_contact_center(cross_m3m4, via_offset, rotate=True)
            self.add_rect(layer, vector(pin.cx() - 0.5 * dest_rail_width, dest_rail_y),
                          width=dest_rail_width, height=dest_rail_height)
            via, rotate = (cross_m2m3, False) if layer == METAL2 else (cross_m3m4, True)
            self.add_cross_contact_center(via, vector(pin.cx(), y_offset), rotate=rotate)

    def join_pins(self, y_index=None, pin_name=None, pins=None):
        if y_index is None:
            y_index = self.rail_y_index
        y_offset = self.get_rail_y(y_index)
        if pins is None:
            pins = [x.get_pin(pin_name) for x in self.bank_insts]

        def get_layer_via(layer_):
            if layer_ == METAL2:
                return cross_m2m3, False
            else:
                return cross_m3m4, True

        for pin in pins:
            y_end = self.get_pin_y_edge(pin)

            if y_end < self.mid_rail_y:
                layer = METAL2
                rail_y = y_offset + 0.5 * m2m3.h_1
            else:
                layer = METAL4
                rail_y = y_offset - m3m4.h_2
            if not layer == pin.layer:
                self.pins_to_mid_rails.append([pin, y_offset])
            else:
                layer = pin.layer
                self.add_rect(pin.layer, vector(pin.lx(), rail_y),
                              width=pin.width(),
                              height=y_end - rail_y)
                via, rotate = get_layer_via(layer)
                self.add_cross_contact_center(via, vector(pin.cx(), y_offset), rotate=rotate)
        via_x_ext = 0.5 * max(m2m3.h_2, m3m4.h_1)
        min_x = min(map(lambda x: x.cx(), pins)) - via_x_ext
        max_x = max(map(lambda x: x.cx(), pins)) + via_x_ext
        if pin_name is not None:
            self.add_layout_pin(pin_name, METAL3,
                                vector(min_x, y_offset - 0.5 * rail_width),
                                width=max_x - min_x, height=rail_width)

    def get_pin_y_edge(self, pin):
        if pin.by() > self.mid_rail_y:
            return utils.round_to_grid(pin.by())
        return utils.round_to_grid(pin.uy())

    def join_m4_gnd_pins(self):
        gnd_rail_indices = [-2, 0, 2]
        for bank in self.bank_insts:
            # only select pins that are at least as low as DATA[0]
            data_pin = bank.get_pin("DATA[0]")
            reference_y = self.get_pin_y_edge(data_pin)
            gnd_pins = [pin for pin in bank.get_pins("gnd") if pin.layer == METAL4]
            m4_pins = []
            for pin in gnd_pins:
                y_edge = self.get_pin_y_edge(pin)
                if self.mid_rail_y < y_edge <= reference_y:
                    m4_pins.append(pin)
                elif self.mid_rail_y > y_edge >= reference_y:
                    m4_pins.append(pin)
            for y_index in gnd_rail_indices:
                self.join_pins(y_index, pins=m4_pins)

        for y_index in gnd_rail_indices:
            y_offset = self.get_rail_y(y_index) - 0.5 * rail_width
            self.add_layout_pin("gnd", METAL3, vector(0, y_offset), width=self.width,
                                height=rail_width)

    @staticmethod
    def alternate_bits(bits):
        num_bits = len(bits)
        half_bits = math.floor(num_bits / 2)
        alt_bits = []
        for i in range(half_bits):
            alt_bits.append(bits[i + half_bits])
            alt_bits.append(bits[half_bits - i - 1])
        if num_bits % 2 == 1:
            alt_bits.append(bits[-1])
        return alt_bits

    def join_address_pins(self):

        # bank sels
        self.bank_sel_pins = [f"bank_sel_b[{bank_index}]" for bank_index in range(4)]
        for bank_index in range(4):
            bank_sel = self.bank_sel_pins[bank_index]
            self.connection_replacements[bank_index]["csb"] = bank_sel
            self.join_pins(pin_name=bank_sel, pins=[self.bank_insts[bank_index].get_pin("csb")])
            self.increment_y_index()

        bits = list(range(PinAssignmentsMixin.num_address_pins))
        alt_bits = self.alternate_bits(bits)
        for bit in alt_bits:
            all_pins = []
            pin_name = f"ADDR[{bit}]"
            for bank in self.bank_insts:
                if pin_name.lower() in bank.mod.pins:
                    pin = bank.get_pin(pin_name)
                    all_pins.append(pin)
            self.join_pins(pins=all_pins, pin_name=pin_name)

            self.increment_y_index()

    def join_data_pins(self):

        pin_names = []
        num_data = self.num_data_out - 1

        assigned_bits = []
        un_assigned_bits = []

        for bank in self.bank_insts:
            word_size = bank.mod.word_size
            bit_spacing = max(1, word_size / num_data)
            debug.info(2, "Bit spacing for %s is %.3g", bank.mod.name, bit_spacing)
            tentative_bits = [math.floor((i + 1) * bit_spacing) for i in range(num_data - 1)]
            tentative_bits.append(word_size - 1)
            tentative_bits.append(0)

            tentative_bits = list(sorted(set(tentative_bits)))

            assigned_bits.append(tentative_bits)
            un_assigned_bits.append([x for x in range(word_size)
                                     if x not in tentative_bits])

        for i in range(num_data + 1):
            pin_names.append(("mask", i))
            pin_names.append(("data_out", i))
            pin_names.append(("data", i))

        other_pins = ["data_others", "mask_others", "data_out_others"]
        pin_names.extend([(x, None) for x in other_pins])

        alt_pin_names = self.alternate_bits(pin_names)
        for pin_name, wrapper_bit in alt_pin_names:
            join_pins = True
            pins = []
            if pin_name in other_pins:
                pins = []
                bank_pin_name = pin_name.replace("_others", "")
                for bank_index, bank in enumerate(self.bank_insts):
                    for bank_bit in un_assigned_bits[bank_index]:
                        bank_pin = bank.get_pin(f"{bank_pin_name}[{bank_bit}]")
                        if pin_name == "data_out_others":
                            replacement = f"data_out_internal_{bank_index}[{bank_bit}]"
                            join_pins = False
                        else:
                            replacement = pin_name
                        self.connection_replacements[bank_index][bank_pin.name] = replacement
                        pins.append(bank_pin)
            else:
                wrapper_name = f"{pin_name}[{wrapper_bit}]"
                for bank_index, bank in enumerate(self.bank_insts):
                    if wrapper_bit < len(assigned_bits[bank_index]):
                        bank_bit = assigned_bits[bank_index][wrapper_bit]
                        bank_pin = bank.get_pin(f"{pin_name}[{bank_bit}]")
                        self.connection_replacements[bank_index][bank_pin.name] = wrapper_name
                        pins.append(bank_pin)
                pin_name = wrapper_name
            if join_pins:
                self.join_pins(pin_name=pin_name, pins=pins)
                self.increment_y_index()

    def increment_y_index(self):
        y_index = self.rail_y_index
        if y_index >= 0:
            self.rail_y_index = - y_index
        else:
            self.rail_y_index = -y_index + 1

    def join_bank_pins(self):
        debug.info(1, "Joining sub-bank pins")
        # control rails
        y_indices = [-3, -1, 1, 3]
        pin_names = ["clk", "sense_trig", "web"]
        for pin_name, y_index in zip(pin_names, y_indices):
            self.join_pins(y_index, pin_name=pin_name)

        self.join_m4_gnd_pins()
        self.rail_y_index = 4
        self.join_address_pins()
        self.join_data_pins()
        for bank in self.bank_insts:
            for pin_name in ["vref", "vclamp", "vclampp"]:
                self.copy_layout_pin(bank, pin_name)

    def add_power_grid(self):
        debug.info(1, "Joining sub-banks power grid")
        if OPTS.separate_vdd_write:
            self.vdd_write_pins = ["vdd_write_bl", "vdd_write_br"]
        else:
            self.vdd_write_pins = ["vdd_write"]
        for pin_name in ["vdd_wordline"] + self.vdd_write_pins:
            for bank in self.bank_insts:
                self.copy_layout_pin(bank, pin_name)

        def get_bank_pins(bank_, pin_name_, layer_):
            return [pin for pin in bank_.get_pins(pin_name_) if pin.layer == layer_]

        def copy_pin(pin):
            self.add_layout_pin(pin.name, pin.layer, pin.ll(), pin.width(), pin.height())

        def add_vertical_pin(pin):
            self.add_layout_pin(pin.name, METAL6, vector(pin.lx(), 0),
                                width=pin.width(), height=self.height)

        def add_horizontal_pin(pin):
            self.add_layout_pin(pin.name, METAL5, vector(0, pin.by()),
                                width=self.width, height=pin.height())

        for pin_name in ["vdd", "gnd"]:
            # extend pin to full width or height if it overlaps with an adjacent bank's pin
            # of the same name OR if it  doesn't overlap with the adjacent bank
            # Otherwise, just copy the pin to top level to prevent shorts

            # M5 horizontal pins
            for left_bank, right_bank in [(self.top_left_inst, self.top_right_inst),
                                          (self.bottom_left_inst, self.top_right_inst)]:
                left_pins = get_bank_pins(left_bank, pin_name, METAL5)
                right_pins = get_bank_pins(right_bank, pin_name, METAL5)
                right_mid_y = [round_(pin.cy()) for pin in right_pins]
                left_mid_y = [round_(pin.cy()) for pin in right_pins]
                for left_pin in left_pins:
                    overlaps_right = right_bank.by() <= left_pin.cy() <= right_bank.uy()
                    if round_(left_pin.cy()) in right_mid_y or not overlaps_right:
                        add_horizontal_pin(left_pin)
                    else:
                        copy_pin(left_pin)
                for right_pin in right_pins:
                    overlaps_left = left_bank.by() <= right_pin.cy() <= left_bank.uy()
                    if round_(right_pin.cy()) not in left_mid_y and overlaps_left:
                        copy_pin(right_pin)
                    else:
                        add_horizontal_pin(right_pin)

            # M6 vertical pins
            for bottom_bank, top_bank in [(self.bottom_left_inst, self.top_left_inst),
                                          (self.bottom_right_inst, self.top_right_inst)]:
                bottom_pins = get_bank_pins(bottom_bank, pin_name, METAL6)
                top_pins = get_bank_pins(top_bank, pin_name, METAL6)
                top_mid_x = [round_(pin.cx()) for pin in top_pins]
                bottom_mid_x = [round_(pin.cx()) for pin in bottom_pins]
                for bottom_pin in bottom_pins:
                    overlaps_top = top_bank.lx() <= bottom_pin.cx() <= top_bank.rx()
                    if round_(bottom_pin.cx()) in top_mid_x or not overlaps_top:
                        add_vertical_pin(bottom_pin)
                    else:
                        copy_pin(bottom_pin)
                for top_pin in top_pins:
                    overlaps_bottom = bottom_bank.lx() <= top_pin.cx() <= bottom_bank.rx()
                    if round_(top_pin.cx()) not in bottom_mid_x and overlaps_bottom:
                        copy_pin(top_pin)
                    else:
                        add_vertical_pin(top_pin)

    def get_spice_file(self):
        return os.path.join(caravel_config.spice_dir, f"{self.name}.spice")

    def generate_spice(self):
        file_name = self.get_spice_file()
        self.spice_file_name = file_name
        debug.info(1, "Reram spice file is %s", file_name)
        self.sp_write(file_name)

    def generate_gds(self):
        file_name = os.path.join(caravel_config.gds_dir, f"{self.name}.gds")
        debug.info(1, "Reram gds file is %s", file_name)
        self.gds_write(file_name)

    def get_pin_type(self, pin_name):
        inputs = ["sense_trig", "vref", "vclamp", "vclampp", "web", "clk",
                  "data_others", "mask_others"]

        prefixes = {
            "bank_sel_b[": (INPUT, len(sram_configs)),
            "data[": (INPUT, self.num_data_out),
            "mask[": (INPUT, self.num_data_out),
            "data_out[": (OUTPUT, self.num_data_out),
            "addr[": (INPUT, PinAssignmentsMixin.num_address_pins)
        }

        pin_type = None

        pin_name = pin_name.lower()
        if pin_name in inputs:
            pin_type = INPUT
        elif pin_name in ["vdd", "gnd", "vdd_write", "vdd_wordline", "vdd_write_bl", "vdd_write_br"]:
            pin_type = INOUT
        else:
            for prefix in prefixes:
                if pin_name.startswith(prefix):
                    pin_type = prefixes[prefix][0]
                    width = prefixes[prefix][1]
                    pin_name = f"[{width - 1}:0] {prefix[:-1]}"

        if not pin_type:
            assert False, f"Pin type for {pin_name} not specified"
        return pin_type, pin_name

    def generate_verilog(self):
        file_name = os.path.join(caravel_config.verilog_dir, f"{self.name}.v")
        debug.info(1, "Reram Verilog file is %s", file_name)
        with open(file_name, "w") as f:
            f.write(f"// Generated from OpenRAM\n\n")
            f.write(f"module reram_{self.name} (\n")

            processed_keys = set()
            for pin in self.pins:
                pin_type, pin_name = self.get_pin_type(pin)
                if pin_name in processed_keys:
                    continue
                processed_keys.add(pin_name)
                f.write(f"    {pin_type} {pin_name},\n")

            f.write(f");\n")
