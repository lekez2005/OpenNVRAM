from base.contact import cross_m1m2, m2m3, cross_m2m3, m1m2, m3m4
from base.design import METAL1, METAL3, METAL2, METAL4
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import BaselineBank
from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class MramBank(BaselineBank):
    """bank with thin bitcell not supporting 1 word per row"""
    rwl_driver = wwl_driver = None
    wordline_driver_inst = rwl_driver_inst = wwl_driver_inst = None
    wordline_en_rail = rwl_en_rail = None

    def add_pins(self):
        super().add_pins()
        self.add_pin("vref")

    @staticmethod
    def get_module_list():
        modules = BaselineBank.get_module_list()
        modules = [x for x in modules if x not in ["wordline_driver"]]
        modules.extend(["rwl_driver", "wwl_driver"])
        return modules

    def create_modules(self):
        if not self.is_left_bank:
            self.rwl_driver = self.create_module("rwl_driver", name="rwl_driver",
                                                 rows=self.num_rows,
                                                 buffer_stages=OPTS.wordline_buffers)
            self.wwl_driver = self.create_module("wwl_driver", name="wwl_driver",
                                                 rows=self.num_rows,
                                                 buffer_stages=OPTS.wordline_buffers)
        super().create_modules()

    def create_optimizer(self):
        from modules.mram.sotfet.sotfet_control_buffers_optimizer import \
            SotfetControlBuffersOptimizer
        self.optimizer = SotfetControlBuffersOptimizer(self)

    def create_control_buffers(self):
        self.control_buffers = SotfetMramControlBuffers(self)
        self.add_mod(self.control_buffers)

    def get_non_flop_control_inputs(self):
        """Get control buffers inputs that don't go through flops"""
        precharge_trigger = ["precharge_trig"] * self.control_buffers.use_precharge_trigger
        write_trigger = ["write_trig"] * ("write_trig" in self.control_buffers.pins)
        return ["sense_trig"] + precharge_trigger + write_trigger

    def get_control_rails_base_x(self):
        self.vref_x_offset = self.mid_vdd_offset - self.wide_m1_space - self.bus_width
        return self.vref_x_offset - self.bus_pitch

    def get_top_precharge_pin(self):
        precharge_in_pins = self.precharge_array.get_input_pins()
        top_precharge = max([self.precharge_array_inst.get_pin(x) for x in precharge_in_pins],
                            key=lambda x: x.uy()).name
        if top_precharge == "en":
            top_precharge = "precharge_en_bar"
        return top_precharge

    def get_control_rails_destinations(self):
        destinations = super().get_control_rails_destinations()
        top_precharge = self.get_top_precharge_pin()
        destinations["wwl_en"] = destinations[top_precharge]
        destinations["rwl_en"] = destinations[top_precharge]
        return destinations

    def get_control_rails_order(self, destination_pins, get_top_destination_pin_y):
        rail_names = super().get_control_rails_order(destination_pins, get_top_destination_pin_y)
        top_precharge = self.get_top_precharge_pin()

        # move w/rwl_en to the left of precharge resets
        if self.wwl_driver_inst.lx() > self.rwl_driver_inst.lx():
            enable_pins = ["wwl_en", "rwl_en", top_precharge]
        else:
            enable_pins = ["rwl_en", "wwl_en", top_precharge]

        rail_indices = sorted([rail_names.index(x) for x in enable_pins])
        for i, rail_index in enumerate(rail_indices):
            rail_names[rail_index] = enable_pins[i]
        return rail_names

    @staticmethod
    def get_default_wordline_enables():
        return ["wwl_en", "rwl_en"]

    @staticmethod
    def get_default_left_rails():
        return MramBank.get_default_wordline_enables()

    def add_control_rails(self):
        super().add_control_rails()
        self.wordline_en_rail = self.rwl_en_rail

    def route_vdd_pin(self, pin, add_via=True, via_rotate=90):
        if ("vdd" in self.precharge_array.pins and
                pin in self.precharge_array_inst.get_pins("vdd")):
            via_rotate = 90
        super().route_vdd_pin(pin, add_via, via_rotate)

    def add_wordline_driver(self):
        """ Wordline Driver """
        # calculate space to enable placing one M2 fill
        fill_space = (self.get_parallel_space(METAL2) + self.fill_width +
                      self.get_wide_space(METAL2))

        rwl_connections = []
        wwl_connections = []
        for i in range(self.num_rows):
            rwl_connections.append("dec_out[{}]".format(i))
            wwl_connections.append("dec_out[{}]".format(i))
        for i in range(self.num_rows):
            rwl_connections.append("rwl[{}]".format(i))
            wwl_connections.append("wwl[{}]".format(i))
        rwl_connections.append("rwl_en")
        wwl_connections.append("wwl_en")
        rwl_connections.extend(["vdd", "gnd"])
        wwl_connections.extend(["vdd", "gnd"])

        names = ["rwl_driver", "wwl_driver"]
        connections = [rwl_connections, wwl_connections]
        modules = [self.rwl_driver, self.wwl_driver]

        # arrange based on order of wwl, rwl bitcell pins
        wwl_pin = self.bitcell_array_inst.get_pin("wwl[0]")
        rwl_pin = self.bitcell_array_inst.get_pin("rwl[0]")

        if wwl_pin.cy() > rwl_pin.cy():
            reverse = False
        else:
            names = list(reversed(names))
            connections = list(reversed(connections))
            modules = list(reversed(modules))
            reverse = True

        left_mod, right_mod = modules
        right_x_offset = self.mid_vdd_offset - (right_mod.width + fill_space)
        left_x_offset = right_x_offset - self.wide_m1_space - left_mod.width
        x_offsets = [left_x_offset, right_x_offset]

        insts = []

        for i in range(2):
            inst = self.add_inst(name=names[i], mod=modules[i],
                                 offset=vector(x_offsets[i], self.bitcell_array_inst.by()))
            insts.append(inst)
            self.connect_inst(connections[i])
        self.wordline_driver_inst = min(insts, key=lambda x: x.lx())
        self.wordline_driver = self.wordline_driver_inst.mod
        self.rwl_driver_inst, self.wwl_driver_inst = sorted(insts, key=lambda x: x.lx(),
                                                            reverse=reverse)

    def get_bitcell_array_connections(self):
        connections = self.connections_from_mod(self.bitcell_array,
                                                [])
        return connections

    def route_sense_amp(self):
        self.add_vref_pin()
        super().route_sense_amp()

    def route_external_control_pin(self, pin_name, inst, x_offset, inst_pin_name=None):
        if inst_pin_name is None:
            inst_pin_name = pin_name
        inst_pin = inst.get_pin(inst_pin_name)
        y_offset = self.mid_vdd.by()
        pin = self.add_layout_pin(pin_name, METAL2, offset=vector(x_offset, y_offset),
                                  height=inst_pin.cy() - y_offset,
                                  width=self.bus_width)
        self.add_cross_contact_center(cross_m2m3, offset=vector(pin.cx(), inst_pin.cy()))
        rect_height = min(self.bus_width, inst_pin.height())
        self.add_rect(METAL3, offset=vector(pin.cx(), inst_pin.cy() - 0.5 * rect_height),
                      width=inst_pin.lx() - pin.cx(), height=rect_height)

    def add_vref_pin(self):
        x_offset = self.vref_x_offset
        self.route_external_control_pin("vref", inst=self.sense_amp_array_inst,
                                        x_offset=x_offset)

    def route_bitcell(self):
        """wordline driver wordline to bitcell array wordlines"""
        self.route_bitcell_array_power()

    def route_wordline_driver(self):
        self.route_decoder_in()
        self.route_wordline_in()
        self.route_decoder_enable()
        self.join_wordline_power()
        self.fill_between_wordline_drivers()

    def route_wordline_in(self):
        for row in range(self.num_rows):
            for in_name, driver in zip(["wwl", "rwl"],
                                       [self.wwl_driver_inst,
                                        self.rwl_driver_inst]):
                out_pin = driver.get_pin("wl[{}]".format(row))
                in_pin = self.bitcell_array_inst. \
                    get_pin("{}[{}]".format(in_name, row))
                self.add_rect(METAL1, offset=out_pin.lc(),
                              height=in_pin.by() - out_pin.cy(),
                              width=out_pin.width())
                via_offset = vector(out_pin.cx(), in_pin.cy())
                self.add_contact_center(m1m2.layer_stack, offset=via_offset)
                self.add_cross_contact_center(cross_m2m3, offset=via_offset, rotate=False)
                offset = vector(out_pin.cx() - 0.5 * m2m3.second_layer_height,
                                in_pin.by())
                self.add_rect(METAL3, offset=offset,
                              width=in_pin.lx() - offset.x,
                              height=in_pin.height())

    def join_decoder_in(self):
        left_inst, right_inst = sorted([self.wwl_driver_inst, self.rwl_driver_inst],
                                       key=lambda x: x.lx())
        for row in range(self.num_rows):
            left_in = left_inst.get_pin("in[{}]".format(row))
            right_in = right_inst.get_pin("in[{}]".format(row))
            self.add_rect(METAL3, offset=vector(left_in.lx(), right_in.cy() - 0.5 * self.m3_width),
                          width=right_in.lx() - left_in.lx())
            self.copy_layout_pin(left_inst, "in[{}]".format(row), "dec_out[{}]".format(row))

    def route_decoder_in(self):
        self.join_decoder_in()
        for inst in [self.wwl_driver_inst, self.rwl_driver_inst]:
            for row in range(self.num_rows):
                in_pin = inst.get_pin("in[{}]".format(row))
                offset = vector(in_pin.lx() - 0.5 * m1m2.first_layer_height,
                                in_pin.cy())
                self.add_cross_contact_center(cross_m2m3, offset)
                self.add_cross_contact_center(cross_m1m2, offset, rotate=True)

    def get_decoder_enable_y(self):
        m3_rects = self.wwl_driver_inst.mod.get_layer_shapes(METAL3)
        if m3_rects:
            min_rect = min(m3_rects, key=lambda x: x.by())
            if min_rect.by() <= 0:
                return min_rect.by() - self.bus_pitch + self.wwl_driver_inst.by()

        return min(self.wwl_driver_inst.get_pin("en").by() - self.bus_width,
                   self.wwl_driver_inst.by() - 0.5 * self.rail_height -
                   self.bus_width)

    def route_decoder_enable(self):
        control_rails = ["wwl_en_rail", "rwl_en_rail"]
        driver_instances = [self.wwl_driver_inst, self.rwl_driver_inst]
        if self.rwl_driver_inst.lx() < self.wwl_driver_inst.lx():
            control_rails = list(reversed(control_rails))
            driver_instances = list(reversed(driver_instances))
        base_y = self.get_decoder_enable_y()
        for i in range(2):
            control_rail = getattr(self, control_rails[i])
            enable_in = driver_instances[i].get_pin("en")
            y_offset = base_y - i * self.bus_pitch + 0.5 * self.bus_width

            self.add_rect(METAL2, offset=vector(control_rail.lx(), control_rail.uy()),
                          width=control_rail.width,
                          height=y_offset - control_rail.uy())

            self.add_cross_contact_center(cross_m2m3, offset=vector(control_rail.cx(), y_offset))
            self.add_rect(METAL3, offset=vector(enable_in.cx(), y_offset - 0.5 * self.bus_width),
                          height=self.bus_width, width=control_rail.cx() - enable_in.cx())
            self.add_rect(METAL2, offset=vector(enable_in.lx(), y_offset),
                          width=enable_in.width(),
                          height=enable_in.by() - y_offset)
            self.add_cross_contact_center(cross_m2m3, offset=vector(enable_in.cx(), y_offset))

    def join_wordline_power(self):
        left_inst = min([self.wwl_driver_inst, self.rwl_driver_inst], key=lambda x: x.lx())
        pin_names = ["gnd", "vdd"]
        dest_rail = [self.mid_gnd, self.mid_vdd]
        for i in range(2):
            pin_name = pin_names[i]
            for pin in left_inst.get_pins(pin_name):
                self.add_rect(pin.layer, offset=vector(left_inst.lx(), pin.by()),
                              height=pin.height(),
                              width=dest_rail[i].rx() - left_inst.lx())
                self.add_power_via(pin, dest_rail[i], via_rotate=90)

    def fill_between_wordline_drivers(self):
        pass

    def get_intra_array_grid_top(self):
        # TODO detect if bitcell_array/precharge M4 would clash with power rails
        # below column mux
        power_pins = (self.sense_amp_array_inst.get_pins("vdd") +
                      self.sense_amp_array_inst.get_pins("gnd"))
        return max(power_pins, key=lambda x: x.uy()).uy()

    def get_inter_array_power_grid_offsets(self):
        cell_offsets = self.bitcell_array.bitcell_offsets
        empty_indices = (set(range(self.num_cols)).
                         difference(set(self.occupied_m4_bitcell_indices)))

        if self.words_per_row > 1:
            bit_zero_indices = range(0, self.num_cols, self.words_per_row)
            empty_indices = empty_indices.difference(set(bit_zero_indices))
        empty_indices = list(empty_indices)

        cell_spacing = OPTS.bitcell_vdd_spacing
        candidates = list(range(cell_spacing, self.num_cols, cell_spacing))
        power_grid_indices = set()
        for candidate in candidates:
            closest = empty_indices[min(range(len(empty_indices)),
                                        key=lambda i: abs(empty_indices[i]
                                                          - candidate))]
            power_grid_indices.add(closest)

        self.occupied_m4_bitcell_indices.extend(candidates)
        power_grid_indices = list(sorted(power_grid_indices))
        mid_x_offsets = [x + 0.5 * self.bitcell.width for x in cell_offsets]

        power_groups = {"vdd": [], "gnd": []}

        rail_width = m3m4.second_layer_height
        space = 0.5 * self.get_parallel_space(METAL4)

        for index in power_grid_indices:
            mid_x = mid_x_offsets[index]
            power_groups["vdd"].append(mid_x - space - rail_width)
            power_groups["gnd"].append(mid_x + space)
        return power_groups
