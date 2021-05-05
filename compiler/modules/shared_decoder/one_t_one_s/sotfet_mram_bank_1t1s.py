import debug
from base.contact import cross_m1m2, m2m3, cross_m2m3, m1m2
from base.design import METAL1, METAL3, METAL2, ACTIVE
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from modules.baseline_bank import BaselineBank
from modules.shared_decoder.one_t_one_s.sotfet_mram_control_buffers_1t1s import SotfetMramControlBuffers1t1s
from modules.shared_decoder.sotfet.sotfet_mram_bank import SotfetMramBank


class SotfetMramBank1t1s(SotfetMramBank):
    def create_control_buffers(self):
        self.control_buffers = SotfetMramControlBuffers1t1s(self)
        self.add_mod(self.control_buffers)

    @staticmethod
    def get_module_list():
        return SotfetMramBank.get_module_list() + ["br_precharge_array"]

    def connect_inst(self, args, check=True):
        if args and self.insts[-1].name in ["wwl_driver", "rwl_driver"]:
            args.append("rw")
        super().connect_inst(args, check)

    def add_pins(self):
        super().add_pins()
        self.add_pin("rw")

    def get_control_rails_destinations(self):
        destinations = super().get_control_rails_destinations()
        destinations["wwl_en"] = destinations["precharge_en_bar"]
        destinations["rwl_en"] = destinations["precharge_en_bar"]
        return destinations

    def get_vertical_instance_stack(self):
        stack = super().get_vertical_instance_stack()
        stack.insert(stack.index(self.precharge_array_inst), self.br_precharge_array_inst)
        return stack

    @staticmethod
    def get_default_wordline_enables():
        return ["wwl_en", "rwl_en"]

    def route_precharge(self):
        if self.col_mux_array_inst is not None:
            self.route_all_instance_power(self.br_precharge_array_inst)
            BaselineBank.route_precharge(self)
            return
        debug.info(1, "Route Precharge")
        self.join_bitlines(top_instance=self.bitcell_array_inst, top_suffix="",
                           bottom_instance=self.precharge_array_inst,
                           bottom_suffix="", word_size=self.num_cols)
        y_offset = self.get_m2_m3_below_instance(self.br_precharge_array_inst)
        y_shift = y_offset - self.br_precharge_array_inst.get_pin("br[0]").by()

        self.join_bitlines(top_instance=self.br_precharge_array_inst, top_suffix="",
                           bottom_instance=self.sense_amp_array_inst,
                           bottom_suffix="", y_shift=y_shift)
        for pin_name in ["bl", "br"]:
            for col in range(self.num_cols):
                full_pin_name = "{}[{}]".format(pin_name, col)
                sense_pin = self.sense_amp_array_inst.get_pin(full_pin_name)
                precharge_pin = self.br_precharge_array_inst.get_pin(full_pin_name)
                self.add_path(METAL2, [vector(sense_pin.cx(), y_offset),
                                       vector(sense_pin.cx(), precharge_pin.by())])
        self.route_all_instance_power(self.precharge_array_inst)

    def route_sense_amp(self):
        self.add_vref_pin()
        BaselineBank.route_sense_amp(self)

    def route_wwl_in(self):
        self.join_rw_pin()

        left_inst, right_inst = sorted([self.wwl_driver_inst, self.rwl_driver_inst],
                                       key=lambda x: x.lx())

        # left_inst.mod.add_body_taps()

        if left_inst == self.wwl_driver_inst:
            pin_names = ["wwl", "rwl"]
        else:
            pin_names = ["rwl", "wwl"]

        for row in range(self.num_rows):
            right_pin = right_inst.get_pin("wl[{}]".format(row))
            right_bitcell_pin = self.bitcell_array_inst.get_pin(
                "{}[{}]".format(pin_names[1], row))
            bend_x = right_bitcell_pin.lx() - self.line_end_space - 0.5 * self.m1_width
            self.add_path(METAL1, [right_pin.rc(), vector(bend_x, right_pin.cy()),
                                   vector(bend_x, right_bitcell_pin.cy()),
                                   right_bitcell_pin.lc()])

            left_bitcell_pin = self.bitcell_array_inst.get_pin(
                "{}[{}]".format(pin_names[0], row))
            left_pin = left_inst.get_pin("wl[{}]".format(row))
            if left_bitcell_pin.cy() > right_bitcell_pin.cy():
                y_offset = left_pin.uy()
            else:
                y_offset = left_pin.by()
            self.add_cross_contact_center(cross_m2m3, vector(left_pin.cx(), y_offset),
                                          fill=False)
            x_offset = right_pin.rx() + self.get_via_space(m1m2)
            self.add_rect(METAL3,
                          offset=vector(left_pin.cx(), y_offset - 0.5 * self.m3_width),
                          width=x_offset - left_pin.cx())
            via_offset = vector(x_offset, y_offset - 0.5 * m1m2.height)
            self.add_contact(m1m2.layer_stack, via_offset)
            self.add_contact(m2m3.layer_stack, via_offset)

            self.add_path(METAL1, [vector(x_offset, y_offset),
                                   vector(bend_x, y_offset),
                                   vector(bend_x, left_bitcell_pin.cy()),
                                   left_bitcell_pin.lc()])
            _, fill_height = self.calculate_min_area_fill(self.m2_width, layer=METAL2)
            self.add_rect_center(METAL2,
                                 offset=vector(x_offset + 0.5 * self.m2_width, y_offset),
                                 width=self.m2_width, height=fill_height)

    def route_rwl_in(self):
        pass

    def route_decoder_in(self):
        super().route_decoder_in()
        fill_height = m2m3.second_layer_height
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)
        for inst in [self.wwl_driver_inst, self.rwl_driver_inst]:
            for row in range(self.num_rows):
                in_pin = inst.get_pin("in[{}]".format(row))
                offset = vector(in_pin.cx(), in_pin.cy())
                self.add_cross_contact_center(cross_m2m3, offset)
                self.add_cross_contact_center(cross_m1m2, offset, rotate=True)
                self.add_rect_center(METAL2, offset, width=fill_width,
                                     height=fill_height)

    def join_rw_pin(self):
        y_offset = self.get_decoder_enable_y() - 2 * self.bus_pitch - 0.5 * self.bus_width
        left_inst, right_inst = sorted([self.wwl_driver_inst, self.rwl_driver_inst],
                                       key=lambda x: x.lx())
        left_pin = left_inst.get_pin("rw")
        right_pin = right_inst.get_pin("rw")
        x_offset = left_inst.lx()
        self.add_layout_pin("rw", METAL3, offset=vector(x_offset, y_offset),
                            width=right_pin.cx() - x_offset, height=self.bus_width)
        for pin in [left_pin, right_pin]:
            self.add_rect(METAL2, offset=vector(pin.lx(), y_offset), width=pin.width(),
                          height=pin.by() - y_offset)
            self.add_cross_contact_center(cross_m2m3,
                                          offset=vector(pin.cx(),
                                                        y_offset + 0.5 * self.bus_width))

    def fill_between_wordline_drivers(self):
        # fill between rwl and wwl
        fill_rects = create_wells_and_implants_fills(
            self.rwl_driver.logic_buffer.buffer_mod.module_insts[-1].mod,
            self.wwl_driver.logic_buffer.logic_mod)

        for row in range(self.num_rows):
            for fill_rect in fill_rects:
                if fill_rect[0] == ACTIVE:
                    continue
                if row % 2 == 0:
                    fill_rect = (fill_rect[0], self.wwl_driver.logic_buffer.height -
                                 fill_rect[2],
                                 self.wwl_driver.logic_buffer.height - fill_rect[1])
                y_shift = (self.wwl_driver_inst.by() +
                           row * self.rwl_driver.logic_buffer.height)
                self.add_rect(fill_rect[0], offset=vector(self.rwl_driver_inst.rx(),
                                                          y_shift + fill_rect[1]),
                              height=fill_rect[2] - fill_rect[1],
                              width=(self.wwl_driver_inst.lx() - self.rwl_driver_inst.rx() +
                                     self.wwl_driver.buffer_insts[0].lx()))
