import debug
from base.contact import m2m3, cross_m2m3
from base.design import METAL3, METAL2, NWELL, design, METAL4
from base.vector import vector
from globals import OPTS
from modules.bank_mixins import TwoPrechargeMixin, WordlineVoltageMixin
from modules.baseline_bank import BaselineBank, LEFT_FILL, RIGHT_FILL
from modules.mram.one_t_one_s.sotfet_mram_control_buffers_1t1s import SotfetMramControlBuffers1t1s
from modules.mram.sotfet.mram_bank import MramBank


class SotfetMramBank1t1s(WordlineVoltageMixin, TwoPrechargeMixin, MramBank):

    def add_pins(self):
        super().add_pins()
        self.add_pin("vdd_wordline")

    def create_control_buffers(self):
        self.control_buffers = SotfetMramControlBuffers1t1s(bank=self)
        self.add_mod(self.control_buffers)

    @staticmethod
    def get_module_list():
        return MramBank.get_module_list() + TwoPrechargeMixin.get_mixin_module_list()

    def get_vertical_instance_stack(self):
        stack = super().get_vertical_instance_stack()
        return TwoPrechargeMixin.update_vertical_stack(self, stack)

    def create_br_precharge_array(self):
        self.br_precharge_array = self.create_module('br_precharge_array',
                                                     name="br_precharge_array",
                                                     columns=self.num_cols,
                                                     size=OPTS.discharge_size)

    def get_wwl_connections(self):
        connections = MramBank.get_wwl_connections(self)
        return WordlineVoltageMixin.update_wordline_driver_connections(self, connections)

    def get_right_wordline_offset(self):
        return MramBank.get_right_wordline_offset(self)

    def get_wordline_vdd_offset(self):
        return self.wwl_driver_inst.rx() + 2 * self.get_wide_space(METAL2)

    def join_wordline_power(self):
        WordlineVoltageMixin.route_wordline_power_pins(self, self.wwl_driver_inst)
        for pin in self.rwl_driver_inst.get_pins("vdd"):
            self.add_rect(pin.layer, pin.lr(), height=pin.height(),
                          width=self.mid_vdd.rx() - pin.rx())
            self.add_power_via(pin, self.mid_vdd, 90)

    def route_wordline_in(self):
        if self.wwl_driver_inst.lx() < self.rwl_driver_inst.lx():
            pin_names = ["wwl", "rwl"]
            insts = [self.wwl_driver_inst, self.rwl_driver_inst]
        else:
            pin_names = ["rwl", "wwl"]
            insts = [self.rwl_driver_inst, self.wwl_driver_inst]

        sample_bitcell = self.bitcell_array_inst.get_pin("wwl[0]")

        right_edge_1 = sample_bitcell.lx()
        right_edge_0 = (right_edge_1 - self.get_line_end_space(METAL3) -
                        sample_bitcell.height())

        for i in range(2):
            pin_name = pin_names[i]
            driver_inst = insts[i]
            for row in range(self.num_rows):
                bitcell_pin = self.bitcell_array_inst.get_pin(f"{pin_name}[{row}]")
                driver_pin = driver_inst.get_pin(f"wl[{row}]")
                decoder_pin = driver_inst.get_pin(f"in[{row}]")

                rail_height = decoder_pin.height()

                if i == 0:
                    right_edge = right_edge_0
                    if row % 2 == 1:
                        rail_y = decoder_pin.uy() + self.bus_space
                    else:
                        rail_y = decoder_pin.by() - self.bus_space - rail_height
                else:
                    right_edge = right_edge_1
                    rail_y = decoder_pin.cy() - 0.5 * rail_height

                y_start = min([driver_pin.uy(), driver_pin.by()],
                              key=lambda x: abs(x - rail_y))

                self.add_rect(METAL2,
                              vector(driver_pin.cx() - 0.5 * self.m2_width, y_start),
                              height=rail_y - y_start)
                via_offset = vector(driver_pin.cx(), rail_y + 0.5 * rail_height)
                design.add_cross_contact_center(self, cross_m2m3, via_offset)
                rail_offset = vector(driver_pin.cx() - 0.5 * m2m3.h_2, rail_y)
                self.add_rect(METAL3, rail_offset, height=rail_height,
                              width=right_edge - rail_offset.x)
                edges = [rail_y, rail_y + rail_height, bitcell_pin.by(), bitcell_pin.uy()]
                y_offset = min(edges)
                self.add_rect(METAL3, vector(right_edge, y_offset),
                              width=rail_height, height=max(edges) - y_offset)
                self.add_rect(METAL3, vector(right_edge, bitcell_pin.by()),
                              width=bitcell_pin.lx() - right_edge,
                              height=bitcell_pin.height())

    def route_decoder_in(self):
        self.join_decoder_in()

    def route_precharge_to_sense_or_mux(self):
        if not self.col_mux_array_inst:

            y_offset = self.get_m2_m3_below_instance(self.br_precharge_array_inst, 0)
            for i, pin_name in enumerate(["bl", "br"]):
                precharge_rects = []
                sense_rects = []
                align = LEFT_FILL if i == 0 else RIGHT_FILL
                for col in range(self.num_cols):
                    full_name = f"{pin_name}[{col}]"
                    precharge_pin = self.br_precharge_array_inst.get_pin(full_name)
                    sense_rects.append(self.sense_amp_array_inst.get_pin(full_name))
                    rect = self.add_rect(METAL2, vector(precharge_pin.lx(), y_offset),
                                         width=precharge_pin.width(),
                                         height=precharge_pin.by() - y_offset)
                    precharge_rects.append(rect)
                self.join_rects(precharge_rects, METAL2, sense_rects, METAL4, align)
        else:
            super().route_precharge_to_sense_or_mux()

    def get_intra_array_grid_top(self):
        return self.bitcell_array_inst.by()

    def get_inter_array_power_grid_offsets(self):
        return BaselineBank.get_inter_array_power_grid_offsets(self)
