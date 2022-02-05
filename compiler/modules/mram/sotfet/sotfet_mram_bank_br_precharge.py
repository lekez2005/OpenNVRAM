from base.contact import m2m3, m1m2, cross_m2m3, cross_m1m2
from base.design import METAL1, METAL3, METAL2, ACTIVE, design
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.bank_mixins import TwoPrechargeMixin
from modules.mram.sotfet.mram_bank import MramBank


class SotfetMramBankBrPrecharge(MramBank, TwoPrechargeMixin):
    """
    SotfetMramBank with
        - separate bl precharge and br precharge modules
        - stacked wordline drivers
    """

    def get_vertical_instance_stack(self):
        stack = super().get_vertical_instance_stack()
        return TwoPrechargeMixin.update_vertical_stack(self, stack)

    @staticmethod
    def get_module_list():
        return MramBank.get_module_list() + TwoPrechargeMixin.get_mixin_module_list()

    def get_intra_array_grid_top(self):
        return self.mid_vdd.uy()

    def get_all_power_instances(self):
        return super().get_all_power_instances() + [self.br_precharge_array_inst]

    def get_mid_gnd_offset(self):
        # create space to route wwl and rwl pins
        bitcell = self.bitcell
        m1_extension = min([x.lx() for x in bitcell.get_layer_shapes(METAL1)])

        x_offset = m1_extension - self.get_parallel_space(METAL1) - self.m1_width
        x_offset -= (self.get_parallel_space(METAL1) + self.m1_width)

        return x_offset - self.wide_m1_space - self.vdd_rail_width

    def route_bitcell(self):
        pass

    def route_wordline_in(self):
        self.route_wwl_in()
        self.route_rwl_in()

    def route_wwl_in(self):
        for row in range(self.num_rows):
            wwl_out = self.wwl_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_in = self.bitcell_array_inst.get_pin("wwl[{}]".format(row))
            bitcell_x = (self.mid_gnd.rx() + self.wide_m1_space +
                         self.get_parallel_space(METAL1) + self.m1_width)

            if row % 2 == 1:  # direct m1
                y_offset = wwl_out.cy() - 0.5 * self.m1_width
                self.add_rect(METAL1, offset=vector(wwl_out.rx(), y_offset),
                              width=bitcell_x - wwl_out.rx())
                self.add_rect(METAL1, offset=vector(bitcell_x, y_offset),
                              height=bitcell_in.by() - y_offset)
            else:
                # align with decoder in pin
                decoder_in = self.wwl_driver_inst.get_pin("in[{}]".format(row))
                y_offset = decoder_in.by()
                self.add_contact(m2m3.layer_stack, offset=vector(wwl_out.lx(),
                                                                 wwl_out.by() - 0.5 * m2m3.height))
                self.add_rect(METAL3, offset=vector(wwl_out.lx(), y_offset),
                              height=wwl_out.by() - y_offset)
                x_end = self.wwl_driver_inst.rx() + self.get_parallel_space(METAL2) + 0.5 * self.fill_width
                self.add_rect(METAL3, offset=vector(wwl_out.lx(), y_offset),
                              width=x_end + 0.5 * self.m3_width - wwl_out.lx())

                via_offset = vector(x_end - 0.5 * m2m3.width, y_offset + self.m3_width)
                self.add_contact(m1m2.layer_stack, offset=via_offset)
                self.add_contact(m2m3.layer_stack, offset=via_offset)
                y_offset = y_offset + self.m3_width
                fill_width = self.fill_width
                self.add_rect(METAL2, offset=vector(x_end - 0.5 * fill_width, y_offset),
                              width=fill_width, height=self.fill_height)
                self.add_rect(METAL1, offset=vector(x_end, y_offset),
                              width=bitcell_x - x_end)
                dest_y = bitcell_in.by() if bitcell_in.by() < y_offset else bitcell_in.uy()
                start_y = y_offset + self.m1_width if bitcell_in.by() < y_offset else y_offset
                self.add_rect(METAL1, offset=vector(bitcell_x, start_y), height=dest_y - start_y)
            self.add_rect(METAL1, offset=vector(bitcell_x, bitcell_in.by()),
                          width=bitcell_in.lx() - bitcell_x)

    def route_rwl_in(self):
        for row in range(self.num_rows):
            rwl_out = self.rwl_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_in = self.bitcell_array_inst.get_pin("rwl[{}]".format(row))
            decoder_in = self.wwl_driver_inst.get_pin("in[{}]".format(row))
            bitcell_x = self.mid_gnd.rx() + self.wide_m1_space

            x_end = self.wwl_driver_inst.rx() + self.get_parallel_space(METAL2) + 0.5 * self.fill_width

            if row % 2 == 0:
                # route below decoder in
                y_offset = decoder_in.by() - self.get_parallel_space(METAL3) - 0.5 * m2m3.height
                out_pin_y = rwl_out.by()
                y_bend = decoder_in.by() - self.get_parallel_space(METAL1) - self.m1_width
                fill_y = y_bend + 0.5 * self.m3_width + 0.5 * m2m3.height - self.fill_height
            else:
                # route above decoder in
                y_offset = decoder_in.uy() + self.get_parallel_space(METAL3) + 0.5 * m2m3.height
                out_pin_y = rwl_out.uy()
                y_bend = y_offset + self.m3_width - self.fill_height - self.get_parallel_space(METAL2)
                fill_y = y_bend + 0.5 * self.m3_width - 0.5 * self.fill_height

            self.add_rect(METAL2, offset=vector(rwl_out.lx(), y_offset),
                          height=out_pin_y - y_offset)
            design.add_cross_contact_center(self, cross_m2m3, vector(rwl_out.cx(), y_offset))

            m3_x_offset = x_end - 0.5 * m2m3.height

            self.add_rect(METAL3, offset=vector(rwl_out.cx(), y_offset - 0.5 * self.m3_width),
                          width=m3_x_offset - rwl_out.cx() + self.m3_width)
            self.add_rect(METAL3, offset=vector(m3_x_offset, y_offset), height=y_bend - y_offset)

            # via and fill to M1 at y_bend
            via_offset = vector(x_end, y_bend + 0.5 * self.m3_width)
            design.add_cross_contact_center(self, cross_m2m3, via_offset, rotate=False)
            design.add_cross_contact_center(self, cross_m1m2, via_offset, rotate=True)

            self.add_rect(METAL2, offset=vector(x_end - 0.5 * self.fill_width, fill_y),
                          width=self.fill_width, height=self.fill_height)

            self.add_rect(METAL1, offset=vector(x_end, y_bend), width=bitcell_x - x_end + self.m1_width)
            self.add_rect(METAL1, offset=vector(bitcell_x, y_bend), height=bitcell_in.cy() - y_bend)
            self.add_rect(METAL1, offset=vector(bitcell_x, bitcell_in.by()),
                          width=bitcell_in.lx() - bitcell_x)

    def route_decoder_in(self):
        self.join_decoder_in()

    def mirror_wordline_fill_rect(self, row):
        """Determines if to fill or mirror wordline flip
        None -> No fill, False -> no mirror
        """
        if row % 4 in [1, 3]:
            return None
        return row % 4 == 0

    def fill_between_wordline_drivers(self):
        # fill between rwl and wwl
        fill_rects = create_wells_and_implants_fills(
            self.rwl_driver.logic_buffer.buffer_mod.module_insts[-1].mod,
            self.wwl_driver.logic_buffer.logic_mod)

        bitcell_rows_per_driver = round(self.rwl_driver.logic_buffer.height / self.bitcell.height)

        # self.rwl_driver.add_body_taps()

        for row in range(self.num_rows):
            rect_mirror = self.mirror_wordline_fill_rect(row)
            for fill_rect in fill_rects:
                if fill_rect[0] == ACTIVE:
                    continue
                if rect_mirror is None:
                    continue
                elif rect_mirror:
                    fill_rect = (fill_rect[0], self.wwl_driver.logic_buffer.height -
                                 fill_rect[2],
                                 self.wwl_driver.logic_buffer.height - fill_rect[1])
                y_shift = (self.wwl_driver_inst.by() +
                           int(row / bitcell_rows_per_driver) * self.rwl_driver.logic_buffer.height)
                self.add_rect(fill_rect[0], offset=vector(self.rwl_driver_inst.rx(),
                                                          y_shift + fill_rect[1]),
                              height=fill_rect[2] - fill_rect[1],
                              width=(self.wwl_driver_inst.lx() - self.rwl_driver_inst.rx() +
                                     self.wwl_driver.buffer_insts[0].lx()))
