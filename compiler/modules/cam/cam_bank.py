import debug
from base.contact import cross_m2m3, m1m2, cross_m1m2
from base.design import METAL2, METAL3, METAL1, design, NWELL, PWELL
from base.vector import vector
from base.well_implant_fills import evaluate_vertical_module_spacing, \
    create_wells_and_implants_fills
from globals import OPTS
from modules.baseline_bank import BaselineBank


class CamBank(BaselineBank):

    def get_module_list(self):
        module_list = super().get_module_list()
        module_list = list(set(module_list).difference(["sense_amp_array"]))
        module_list.extend(["ml_precharge_array", "search_sense_amp_array"])
        return module_list

    def create_precharge_array(self):
        self.precharge_array = self.create_module('precharge_array', columns=self.num_cols,
                                                  size=OPTS.precharge_size)
        self.create_matchline_modules()

    def create_matchline_modules(self):
        self.ml_precharge_array = self.create_module('ml_precharge_array', rows=self.num_rows,
                                                     size=OPTS.ml_precharge_size)
        self.search_sense_amp_array = self.create_module('search_sense_amp_array',
                                                         rows=self.num_rows)

    def add_bitcell_array(self):
        super().add_bitcell_array()
        self.add_matchline_modules()

    def add_matchline_modules(self):
        self.add_ml_precharge_array()
        self.add_search_sense_amp_array()

    def route_bitcell(self):
        if self.words_per_row == 1:
            self.route_bitlines_to_bitcell(self.write_driver_array_inst)
        self.route_bitcell_array_power()
        self.route_matchline_modules()

    def route_matchline_modules(self):
        self.route_matchline_precharge()
        self.route_matchline_sense_amp()

    def get_default_wordline_enables(self):
        return ["wordline_en", "ml_precharge_bar", "search_search_en"]

    def get_custom_net_destination(self, net):
        if net in self.get_default_wordline_enables():
            return self.write_driver_array_inst.get_pins("en")
        elif net == "decoder_clk":
            return []
        return None

    def add_left_control_rail(self, rail_name, dest_pins, x_offset, y_offset):
        if rail_name == "search_search_en":
            x_offset = self.search_sense_inst.get_pin("en").cx() - 0.5 * self.bus_width
        super().add_left_control_rail(rail_name, dest_pins, x_offset, y_offset)

    def get_right_vdd_offset(self):
        """x offset for right vdd rail"""
        return max(self.bitcell_array_inst.rx(), self.rightmost_rail.rx(),
                   self.search_sense_inst.rx(),
                   self.control_buffers_inst.rx()) + self.wide_power_space

    def add_sense_amp_array(self):
        self.sense_amp_array_inst = None

    def add_tri_gate_array(self):
        self.tri_gate_array_inst = None

    def get_operation_net(self):
        return "search"

    def get_control_pins(self):
        search_pins = []
        for i in range(self.num_rows):
            search_pins.append("search_out[{0}]".format(i))

        control_pins = super().get_control_pins()
        control_pins += ["search_ref"]
        return search_pins + control_pins

    def calculate_control_buffers_y(self, num_top_rails, num_bottom_rails, module_space):
        y = super().calculate_control_buffers_y(num_top_rails,
                                                num_bottom_rails, module_space)
        # to route mask via
        self.trigate_y += self.bus_pitch
        return y

    def get_mask_flops_y_offset(self, flop=None, flop_tap=None):
        y_space = evaluate_vertical_module_spacing(
            top_modules=[self.msf_mask_in.child_mod],
            bottom_modules=[self.control_buffers.inv], min_space=0)
        return max(self.trigate_y, self.control_buffers_inst.uy() + y_space)

    def get_data_flops_y_offset(self, flop=None, flop_tap=None):
        if not self.has_mask_in:
            return self.get_mask_flops_y_offset(flop, flop_tap)

        y_space = self.calculate_bitcell_aligned_spacing(self.msf_data_in, self.msf_mask_in,
                                                         num_rails=2)
        return self.mask_in_flops_inst.uy() + y_space

    def get_column_mux_array_y(self):
        y_space = self.calculate_bitcell_aligned_spacing(self.column_mux_array,
                                                         self.write_driver_array, num_rails=0)
        return self.write_driver_array_inst.uy() + y_space

    def get_precharge_y(self):
        min_space = -self.column_mux_array.height
        y_space = self.calculate_bitcell_aligned_spacing(self.precharge_array,
                                                         self.column_mux_array, num_rails=0,
                                                         min_space=min_space)
        return self.col_mux_array_inst.uy() + y_space

    def add_precharge_array(self):
        if self.words_per_row == 1:
            self.precharge_array_inst = None
            return
        BaselineBank.add_precharge_array(self)

    def get_bitcell_array_y_offset(self):
        precharge_array_inst = self.precharge_array_inst
        bottom_inst = (precharge_array_inst if precharge_array_inst else
                       self.write_driver_array_inst)

        top_modules = [self.bitcell_array.cell_inst[0][0]]
        if getattr(self.bitcell_array, "body_tap", None):
            top_modules.append(self.bitcell_array.body_tap_insts[0])

        bottom_modules = [bottom_inst.mod.child_mod]
        if getattr(bottom_inst.mod, "body_tap"):
            bottom_modules.append(bottom_inst.mod.body_tap)

        layers = None
        y_space = evaluate_vertical_module_spacing(top_modules, bottom_modules,
                                                   layers=layers)

        ml_space = evaluate_vertical_module_spacing([self.ml_precharge_array.precharge_insts[0]],
                                                    [bottom_inst.mod], layers=[METAL1, METAL3])

        return bottom_inst.uy() + max(y_space, ml_space)

    def get_bitcell_array_connections(self):
        connections = self.connections_from_mod(self.bitcell_array,
                                                [])
        return connections

    def get_ml_precharge_offset(self):
        self.ml_wl_x_offset = (self.mid_vdd_offset - self.get_wide_space(METAL2) -
                               self.m2_width)

        right_most_metal = max(self.ml_precharge_array.get_layer_shapes(METAL1) +
                               self.ml_precharge_array.get_layer_shapes(METAL2),
                               key=lambda x: x.rx())

        space = self.get_line_end_space(METAL2)
        x_offset = self.ml_wl_x_offset - space - right_most_metal.rx()
        return vector(x_offset, self.bitcell_array_inst.by())

    def add_ml_precharge_array(self):
        offset = self.get_ml_precharge_offset()
        self.ml_precharge_array_inst = self.add_inst("ml_precharge_array",
                                                     self.ml_precharge_array,
                                                     offset=offset)
        connections = self.connections_from_mod(self.ml_precharge_array,
                                                [("precharge_en_bar", "ml_precharge_bar")])
        self.connect_inst(connections)

    def get_search_sense_amp_space(self):
        bitcell = self.bitcell_array.cell
        sense_amp = self.search_sense_amp_array.amp

        space_power = False
        for pin_name in ["vdd", "gnd"]:
            for bitcell_pin in bitcell.get_pins(pin_name):
                for sense_pin in sense_amp.get_pins(pin_name):
                    if not bitcell_pin.cy() == sense_pin.cy():
                        space_power = True
        if space_power:
            sample_pin = bitcell.get_pins("gnd")[0]
            rail_width = sample_pin.height()
        else:
            rail_width = self.bus_width

        space = 2 * self.get_parallel_space(METAL3) + rail_width
        if self.has_dummy:
            space = max(space, 2 * self.poly_pitch)

        return space

    def add_search_sense_amp_array(self):
        offset = self.bitcell_array_inst.lr() + vector(self.get_search_sense_amp_space(), 0)
        self.search_sense_inst = self.add_inst(name="search_sense_amps",
                                               mod=self.search_sense_amp_array,
                                               offset=offset)
        self.connect_inst(self.connections_from_mod(self.search_sense_amp_array,
                                                    [("en", "search_search_en"),
                                                     ("dout[", "search_out[")]))

    def get_wordline_offset(self):
        x_offset = self.ml_precharge_array_inst.lx() - self.wordline_driver.width
        return vector(x_offset, self.bitcell_array_inst.by())

    def route_precharge(self):
        if not self.precharge_array_inst:
            return
        super().route_precharge()

    def route_bitlines_to_bitcell(self, bottom_inst):
        all_pins = self.get_bitline_pins(self.bitcell_array_inst,
                                         bottom_inst,
                                         word_size=self.num_cols)
        pin_layer = all_pins[0][0][0].layer
        layer_width = self.get_min_layer_width(pin_layer)
        for top_pins, bottom_pins in all_pins:
            for bitcell_pin, bottom_pin in zip(top_pins, bottom_pins):
                offset = vector(bottom_pin.lx(), bottom_inst.uy())
                self.add_rect(bottom_pin.layer, offset=offset,
                              width=bottom_pin.width(),
                              height=bitcell_pin.by() - offset.y + layer_width)

    def route_precharge_to_bitcell(self):
        self.route_bitlines_to_bitcell(self.precharge_array_inst)

    def route_sense_amp(self):
        pass

    def route_bitcell_array_power(self):
        self.route_all_power_to_rail(self.bitcell_array_inst, "vdd", self.mid_vdd)
        self.route_all_power_to_rail(self.bitcell_array_inst, "gnd", self.mid_gnd)
        for pin_name in ["vdd", "gnd"]:
            sense_pins = self.search_sense_inst.get_pins(pin_name)
            for pin in self.bitcell_array_inst.get_pins(pin_name):
                if not pin.layer == METAL1:
                    continue

                closest_sense = min(sense_pins, key=lambda x: abs(x.cy() - pin.cy()))
                if closest_sense.cy() == pin.cy():
                    self.add_rect(pin.layer, pin.lr(), height=pin.height(),
                                  width=closest_sense.lx() - pin.rx())
                    continue
                width = min(pin.height(), closest_sense.height())
                x_offset = pin.rx() + self.get_wide_space(pin.layer)
                y_offset = pin.cy() - 0.5 * width
                self.add_rect(pin.layer, offset=vector(pin.rx(), y_offset), height=width,
                              width=x_offset - pin.rx() + width)
                self.add_rect(pin.layer, offset=vector(x_offset, closest_sense.cy()),
                              width=width, height=pin.cy() - closest_sense.cy())
                y_offset = closest_sense.cy() - 0.5 * width
                self.add_rect(pin.layer, offset=vector(x_offset, y_offset),
                              height=width, width=closest_sense.lx() - x_offset)

    def get_mask_flop_via_y(self):
        """Get y offset to route m2->m4 mask flop input"""
        return self.get_m2_m3_below_instance(self.mask_in_flops_inst, 0)

    def route_tri_gate(self):
        pass

    def get_decoder_enable_y(self):
        en_pin = self.wordline_driver_inst.get_pin("en")
        precharge_pin = self.ml_precharge_array_inst.get_pin("precharge_en_bar")
        y_offset = min(en_pin.by(), precharge_pin.by())
        y_offset -= (self.get_line_end_space(METAL2) + self.bus_width)
        return y_offset

    def add_m1_m3_via(self, mid_x, mid_y, fill_up):
        # m3 to m1 at x offset
        via_offset = vector(mid_x, mid_y)
        design.add_cross_contact_center(self, cross_m2m3, offset=via_offset)
        cont = design.add_cross_contact_center(self, cross_m1m2, offset=via_offset, rotate=True)
        _, fill_height = self.calculate_min_area_fill(self.m2_width, layer=METAL2)
        if fill_height:
            fill_y = cont.by() if fill_up else cont.uy() - fill_height
            self.add_rect(METAL2, offset=vector(cont.cx() - 0.5 * self.m2_width,
                                                fill_y), height=fill_height)

    def route_wl_to_bitcell(self):
        """Route wordline output to bitcell"""

        precharge_x = self.ml_wl_x_offset

        bitcell_m1 = min(self.bitcell.get_layer_shapes(METAL1),
                         key=lambda x: x.lx())
        bitcell_x = (self.bitcell_array_inst.lx() + bitcell_m1.lx() -
                     self.get_line_end_space(METAL1) - self.m1_width)

        for row in range(self.num_rows):
            pin_name = f"wl[{row}]"
            bitcell_pin = self.bitcell_array_inst.get_pin(pin_name)
            ml_pin = self.ml_precharge_array_inst.get_pin(f"ml[{row}]")

            # driver out to m3 at x_offset
            driver_pin = self.wordline_driver_inst.get_pin(pin_name)

            space = self.get_parallel_space(METAL1) + self.m3_width
            if row % 2 == 0:
                y_offset = min(driver_pin.by() - 0.5 * self.m3_width,
                               ml_pin.uy() - self.m1_width - space)
                start_y = driver_pin.by()
            else:
                y_offset = max(driver_pin.uy() - 0.5 * self.m3_width,
                               ml_pin.by() + space)
                start_y = driver_pin.uy()
            self.add_rect(METAL2, vector(driver_pin.lx(), start_y),
                          width=driver_pin.width(), height=y_offset - start_y)

            via_y = y_offset + 0.5 * self.m3_width
            design.add_cross_contact_center(self, cross_m2m3,
                                            offset=vector(driver_pin.cx(), via_y))
            self.add_rect(METAL3,
                          offset=vector(driver_pin.cx(), via_y - 0.5 * self.m3_width),
                          width=precharge_x - driver_pin.cx())

            self.add_m1_m3_via(precharge_x + 0.5 * m1m2.width, via_y,
                               fill_up=True)
            self.add_path(METAL1, [
                vector(precharge_x, y_offset + 0.5 * self.m1_width),
                vector(bitcell_x + 0.5 * self.m1_width, y_offset + 0.5 * self.m1_width),
                vector(bitcell_x + 0.5 * self.m1_width, bitcell_pin.cy()),
                bitcell_pin.lc()
            ])

    def route_wordline_driver(self):
        debug.info(1, "Route wordline driver")
        self.route_wordline_in()
        self.route_wordline_enable()
        self.route_wl_to_bitcell()

    def route_matchline_precharge(self):
        self.route_all_power_to_rail(self.ml_precharge_array_inst, "vdd", self.mid_vdd)
        self.route_all_power_to_rail(self.ml_precharge_array_inst, "gnd", self.mid_gnd)

        # matchline enable
        enable_pin = self.ml_precharge_array_inst.get_pin("precharge_en_bar")
        enable_rail = getattr(self, "ml_precharge_bar_rail")
        self.add_rect(METAL2, enable_rail.ul(), width=enable_rail.width,
                      height=enable_pin.by() + self.bus_width - enable_rail.uy())
        self.add_rect(METAL2, enable_pin.ll(), width=enable_rail.cx() - enable_pin.lx(),
                      height=self.bus_width)

        precharge_x = self.ml_wl_x_offset
        # matchlines
        for row in range(self.num_rows):
            pin_name = f"ml[{row}]"
            precharge_pin = self.ml_precharge_array_inst.get_pin(pin_name)
            bitcell_pin = self.bitcell_array_inst.get_pin(pin_name)
            if row % 2 == 0:
                y_offset = precharge_pin.uy() - self.m1_width
            else:
                y_offset = precharge_pin.by()
            x_offset = precharge_x + 0.5 * m1m2.width
            self.add_path(METAL1, [
                vector(precharge_pin.rx(), y_offset + 0.5 * self.m1_width),
                vector(x_offset, y_offset + 0.5 * self.m1_width),
                vector(x_offset, bitcell_pin.cy())
            ])
            self.add_m1_m3_via(x_offset, bitcell_pin.cy(), fill_up=True)
            #     vector(bitcell_x, bitcell_pin.cy())
            # ])
            self.add_rect(METAL3,
                          vector(x_offset, bitcell_pin.cy() - 0.5 * self.m3_width),
                          width=bitcell_pin.lx() - x_offset, height=self.m3_width)

    def route_matchline_sense_amp(self):
        self.route_all_power_to_rail(self.search_sense_inst, "vdd", self.right_vdd)
        self.route_all_power_to_rail(self.search_sense_inst, "gnd", self.right_gnd)

        # fill NWELL
        layers = [NWELL, PWELL] if self.has_pwell else [NWELL]
        fills = create_wells_and_implants_fills(self.bitcell, self.search_sense_amp_array.amp,
                                                layers=layers)
        cell_y_offsets = self.search_sense_amp_array.cell_y_offsets
        for layer, rect_bottom, rect_top, left_mod_rect, right_mod_rect in fills:
            fill_height = rect_top - rect_bottom
            x_offset = (self.bitcell_array_inst.rx() +
                        left_mod_rect.rx() - self.bitcell.width)
            width = self.search_sense_inst.lx() + right_mod_rect.lx() - x_offset
            for row in range(self.num_rows):
                y_base = self.bitcell_array_inst.by() + cell_y_offsets[row]
                if row % 2 == 0:
                    y_offset = y_base + self.bitcell.height - rect_top
                else:
                    y_offset = y_base + rect_bottom
                self.add_rect(layer, vector(x_offset, y_offset), width=width,
                              height=fill_height)

        for row in range(self.num_rows):
            pin_name = f"ml[{row}]"
            sense_pin = self.search_sense_inst.get_pin(pin_name)
            bitcell_pin = self.bitcell_array_inst.get_pin(pin_name)
            x_offset = 0.5 * (sense_pin.lx() + bitcell_pin.rx())
            self.add_path(bitcell_pin.layer, [
                bitcell_pin.rc(),
                vector(x_offset, bitcell_pin.cy()),
                vector(x_offset, sense_pin.cy()),
                sense_pin.lc()
            ])

    def add_m2m4_power_rails_vias(self):
        precharge_array_inst = self.precharge_array_inst
        if not precharge_array_inst:
            self.precharge_array_inst = self.write_driver_array_inst
        super().add_m2m4_power_rails_vias()
        self.precharge_array_inst = precharge_array_inst
