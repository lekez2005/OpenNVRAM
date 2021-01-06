from base import utils
from base.contact import m2m3, m1m2, m3m4, contact
from base.vector import vector
from modules.sotfet.cmos.sw_control_buffers import SwControlBuffers
from modules.sotfet.sf_cam_bank import SfCamBank
from tech import drc


class SwCamBank(SfCamBank):

    def create_control_buffers(self):
        self.control_buffers = SwControlBuffers()
        self.add_mod(self.control_buffers)

    def route_layout(self):
        super().route_layout()
        self.connect_buffer_bitlines()

    def add_wordline_pins(self):
        pass

    def get_collisions(self):
        bitline_en_pin = self.bitline_logic_array_inst.get_pin("en")

        return [
            (self.control_buffers_inst.by(), self.mask_in_flops_inst.by()),

            (bitline_en_pin.uy(), bitline_en_pin.by()),

        ]

    def create_wordline_driver(self):
        pass

    def route_wordline_in(self):
        pass

    def get_data_flops_y_offset(self):
        clk_pin = self.msf_data_in.ms.get_pin("clk")
        top_gnd = max(self.msf_data_in.ms.get_pins("gnd"), key=lambda x: x.uy())
        clk_extension = clk_pin.by()
        gnd_extension = top_gnd.uy() - self.msf_data_in.ms.height

        y_space = -clk_extension + gnd_extension + self.parallel_line_space

        return self.mask_in_flops_inst.by() + self.msf_data_in.height + y_space

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        top_bitcell_implant = max(self.bitcell.get_gds_layer_rects("pimplant") +
                                  self.bitcell_array.body_tap.get_gds_layer_rects("nimplant"), key=lambda x: x.uy())
        bitcell_extension = top_bitcell_implant.uy() - self.bitcell.height

        top_buffer = self.bitline_buffer_array.bitline_buffer.out_buffer
        buffer_extension = max(top_buffer.get_layer_shapes("pimplant"), key=lambda x: x.uy()).uy() - top_buffer.height

        total_space = bitcell_extension + buffer_extension + self.implant_space

        offset = self.bitline_buffer_array_inst.ul() + vector(0, total_space)

        self.bitcell_array_inst = self.add_inst(name="bitcell_array", mod=self.bitcell_array, offset=offset)
        connections = []
        for i in range(self.num_cols):
            connections.append("bl[{0}]".format(i))
            connections.append("br[{0}]".format(i))
        for j in range(self.num_rows):
            connections.append("wl[{0}]".format(j))
            connections.append("ml[{0}]".format(j))
        connections.extend(["vdd", "gnd"])
        self.connect_inst(connections)

    def add_wordline_driver(self):
        """ Wordline Driver """

        # The wordline driver is placed to the right of the main decoder width.
        # This means that it slightly overlaps with the hierarchical decoder,
        # but it shares power rails. This may differ for other decoders later...
        self.wordline_driver_inst = self.add_inst(name="wordline_driver", mod=self.wordline_driver,
                                                  offset=vector(self.ml_precharge_array_inst.lx() -
                                                                self.wordline_driver.width,
                                                                self.bitcell_array_inst.by()))
        temp = []
        for i in range(self.num_rows):
            temp.append("dec_out[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("wl[{0}]".format(i))
        temp.append(self.prefix + "wordline_en")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def connect_matchlines(self):
        for row in range(self.num_rows):
            # join matchlines
            precharge_ml = self.ml_precharge_array_inst.get_pin("ml[{}]".format(row))
            bitcell_ml = self.bitcell_array_inst.get_pin("ml[{}]".format(row))\

            y_offset = bitcell_ml.by()
            via_x_offset = bitcell_ml.lx() - self.line_end_space - m2m3.height

            bend_x = precharge_ml.rx() + self.parallel_line_space

            if row % 2 == 0:
                self.add_rect("metal1", offset=precharge_ml.ul() - vector(0, self.m2_width),
                              width=bend_x - precharge_ml.lx() + self.m1_width)
                self.add_rect("metal1", offset=vector(bend_x, precharge_ml.uy()),
                              height=bitcell_ml.uy() - precharge_ml.uy())
                self.add_rect("metal1", offset=vector(bend_x, y_offset), width=via_x_offset - bend_x)
            else:
                self.add_rect("metal1", offset=precharge_ml.lr(), width=bend_x - precharge_ml.rx() + self.m1_width)
                self.add_rect("metal1", offset=vector(bend_x, y_offset),
                              height=precharge_ml.by() - y_offset)
                self.add_rect("metal1", offset=vector(bend_x, y_offset), width=via_x_offset - bend_x)

            self.add_contact(m1m2.layer_stack, offset=vector(via_x_offset, y_offset), rotate=90)
            self.add_contact(m2m3.layer_stack, offset=vector(via_x_offset, y_offset), rotate=90)

            self.add_rect("metal3", offset=vector(via_x_offset, bitcell_ml.by()), width=bitcell_ml.lx()-via_x_offset)
            m2_fill_height = m2m3.second_layer_height
            m2_fill_height, m2_fill_width = self.calculate_min_m1_area(m2_fill_height, self.m2_width)

            y_offset = bitcell_ml.cy() - 0.5*m2_fill_height
            x_offset = via_x_offset - 0.5*(m2m3.second_layer_height + m2_fill_width)
            self.add_rect("metal2", offset=vector(x_offset, y_offset), height=m2_fill_height, width=m2_fill_width)

            # bitcell ml to sense_amp
            sense_amp_ml = self.search_sense_inst.get_pin("ml[{}]".format(row))
            if row % 2 == 0:
                self.add_rect("metal3", offset=vector(sense_amp_ml.ll()), height=bitcell_ml.uy()-sense_amp_ml.by())
            else:
                self.add_rect("metal3", offset=bitcell_ml.lr(), height=sense_amp_ml.uy()-bitcell_ml.by())

    def route_wordline_driver(self):
        # connect wordline en to rail
        en_rail = getattr(self, "wordline_en_rail")
        en_pin = self.wordline_driver_inst.get_pin("en")

        self.add_contact(m2m3.layer_stack, offset=en_rail.ll())

        y_offset = en_pin.by() - self.wide_m1_space - self.m3_width
        self.add_rect("metal2", offset=vector(en_pin.lx(), y_offset), height=en_pin.by() - y_offset)
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), width=en_rail.rx() - en_pin.lx())
        self.add_rect("metal2", offset=en_rail.ul(), height=y_offset - en_rail.uy())
        self.add_contact(m2m3.layer_stack, offset=vector(en_pin.lx(), y_offset))
        self.add_contact(m2m3.layer_stack, offset=vector(en_rail.lx(), y_offset - m2m3.height + self.m3_width))

        # route wl pin
        via_x = self.mid_vdd.lx() - self.parallel_line_space - self.m2_width
        fill_height = utils.ceil(self.minarea_metal1_minwidth/self.m2_width)

        decoder_via_x = self.wordline_driver_inst.get_pin("en").rx() + self.line_end_space + m1m2.first_layer_height

        for row in range(self.num_rows):
            driver_pin = self.wordline_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_pin = self.bitcell_array_inst.get_pin("wl[{}]".format(row))

            if row % 2 == 0:
                via_y = driver_pin.by() - 0.5 * m2m3.height
            else:
                via_y = driver_pin.uy() - 0.5 * m2m3.height

            x_offset = self.mid_vdd.lx() - self.wide_m1_space - self.m2_width
            self.add_rect("metal3", offset=vector(driver_pin.rx(),
                                                  via_y + 0.5*(m2m3.height-self.m3_width)),
                          width=x_offset - driver_pin.rx())

            via_offset = vector(driver_pin.lx(), via_y)
            self.add_contact(m2m3.layer_stack, offset=via_offset)

            m2_fill_width = self.line_end_space
            m2_fill_height = utils.ceil(self.minarea_metal1_contact / m2_fill_width)

            fill_y = via_y + 0.5 * m2m3.height - 0.5 * m2_fill_height

            fill_x = x_offset + self.m2_width - m2_fill_width

            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, via_offset.y))
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_offset.y))

            self.add_rect("metal2", offset=vector(fill_x, fill_y),
                          width=m2_fill_width, height=m2_fill_height)

            self.add_rect("metal1", offset=vector(x_offset, via_offset.y),
                          height=bitcell_pin.cy() - via_offset.y)

            self.add_rect("metal1", offset=vector(x_offset, bitcell_pin.by()),
                          width=bitcell_pin.lx() - x_offset)

            # route decoder output
            decoder_pin = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            driver_in_pin = self.wordline_driver_inst.get_pin("in[{}]".format(row))
            self.add_rect("metal1", offset=decoder_pin.ll(), width=decoder_via_x - decoder_pin.lx())
            via_y = decoder_pin.by() + 0.5 * self.m2_width
            self.add_contact_center(m1m2.layer_stack,
                                    offset=vector(decoder_via_x + 0.5 * self.m2_width, via_y),
                                    rotate=90)
            self.add_path("metal2",
                          [vector(decoder_via_x + 0.5 * m1m2.second_layer_height, via_y),
                           driver_in_pin.center()])
            self.add_contact_center(m1m2.layer_stack, offset=driver_in_pin.center())

    def add_bitline_en_rail(self, base_y, rail_x):
        y_offset = base_y
        top_pin = max(self.bitline_logic_array_inst.get_pins("en"), key=lambda x: x.uy())
        self.bitline_en_rail = self.add_rect("metal2", offset=vector(rail_x, y_offset),
                                             height=top_pin.uy() - y_offset)

    def route_flops(self):
        # connect bitline logic out to bitline buffer in
        for col in range(self.num_cols):
            for pin_name in ["bl", "br"]:
                suffix = "[{}]".format(col)
                buffer_pin = self.bitline_buffer_array_inst.get_pin(pin_name + "_in" + suffix)
                logic_pin = self.bitline_logic_array_inst.get_pin(pin_name + suffix)

                if logic_pin.lx() < buffer_pin.lx():
                    self.add_rect("metal3", offset=vector(logic_pin.lx(), buffer_pin.by()),
                                  width=buffer_pin.rx() - logic_pin.lx())
                else:
                    self.add_rect("metal3", offset=vector(buffer_pin.lx(), buffer_pin.by()),
                                  width=logic_pin.rx()-buffer_pin.lx())

        # connect mask flops to bitline logic input
        for col in range(self.num_cols):
            flop_pin = self.mask_in_flops_inst.get_pin("dout" + "[{}]".format(col))
            logic_pin = self.bitline_logic_array_inst.get_pin("mask" + "[{}]".format(col))

            via_offset = flop_pin.ul() - vector(0, m3m4.height)
            self.add_contact(m2m3.layer_stack, offset=via_offset)
            self.add_contact(m3m4.layer_stack, offset=via_offset)

            y_offset = flop_pin.uy()-self.m4_width
            self.add_rect("metal4", offset=vector(logic_pin.lx(), y_offset),
                          height=logic_pin.by() - y_offset)
            self.add_rect("metal4", offset=vector(flop_pin.lx(), y_offset),
                          width=logic_pin.cx()-flop_pin.lx())
            fill_height = m2m3.height
            fill_width = utils.ceil(drc["minarea_metal3_drc"]/fill_height)
            self.add_rect_center("metal3", offset=vector(flop_pin.cx(), via_offset.y+0.5*m2m3.height),
                                 height=fill_height, width=fill_width)

    def connect_buffer_bitlines(self):
        for col in range(self.num_cols):
            for pin_name in ["bl", "br"]:
                suffix = "[{}]".format(col)
                buffer_pin = self.bitline_buffer_array_inst.get_pin(pin_name + "_out" + suffix)
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name + suffix)

                self.add_rect(buffer_pin.layer, offset=buffer_pin.ul(),
                              height=bitcell_pin.by()-buffer_pin.uy())

    def route_wordline_gnd(self):
        for pin in self.wordline_driver_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=pin.lr(),
                          width=self.mid_gnd.cx() - pin.rx(), height=pin.height())
            self.add_power_via(pin, self.mid_gnd, via_rotate=90)

    def route_flop_gnd(self):
        # flops: vdd and clk too close together
        sample_via = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in [self.mask_in_flops_inst, self.data_in_flops_inst]:
            for pin in instance.get_pins("gnd"):
                self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), pin.by()),
                              width=self.right_gnd.rx() - self.mid_gnd.lx(), height=pin.height())
                via_y = pin.uy() - 0.5 * sample_via.width

                self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_gnd.cx(), via_y),
                                        size=[2, 1], rotate=90)

    def route_bitline_gnds(self):
        for instance in [self.bitline_buffer_array_inst]:
            for pin in instance.get_pins("gnd"):
                self.route_gnd_pin(pin, via_rotate=90)

    def route_vdd_supply(self):
        super().route_vdd_supply()
        # bitcell vdd
        for pin in self.bitcell_array_inst.get_pins("vdd"):
            self.add_rect("metal1", offset=vector(self.mid_vdd.lx(), pin.by()),
                          width=pin.lx() - self.mid_vdd.lx(), height=pin.height())
            self.add_power_via(pin, self.mid_vdd, via_rotate=90)

