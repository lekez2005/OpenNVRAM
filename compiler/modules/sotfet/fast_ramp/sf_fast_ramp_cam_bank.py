from base import utils
from base.contact import m2m3, m1m2
from base.design import METAL1, METAL3, METAL2
from base.vector import vector
from globals import OPTS
from modules.sotfet.cmos.sw_control_buffers import SwControlBuffers
from modules.sotfet.sf_cam_bank import SfCamBank


class SfFastRampCamBank(SfCamBank):

    def add_wordline_pins(self):
        pass

    def route_control_buffer(self):
        super().route_control_buffer()
        if self.double_control_buffer:
            for pin_name in ["vdd", "gnd"]:
                all_pins = self.control_buffers_inst.get_pins(pin_name)
                bottom_pin = min(all_pins, key=lambda x: x.by())
                if pin_name == "vdd":
                    self.route_vdd_pin(bottom_pin)
                else:
                    self.route_gnd_pin(bottom_pin)

    def create_control_buffers(self):
        if self.num_cols <= 40:
            OPTS.control_buffers_num_rows = 2
            self.double_control_buffer = True
        else:
            OPTS.control_buffers_num_rows = 1
            self.double_control_buffer = False
        self.control_buffers = SwControlBuffers()
        self.add_mod(self.control_buffers)

    def get_control_rails_destinations(self):
        if self.double_control_buffer:
            destination_pins = {
                "clk_buf": self.mask_in_flops_inst.get_pins("clk") +
                           self.data_in_flops_inst.get_pins("clk"),
            }
        else:
            destination_pins = {
                "clk_buf": self.mask_in_flops_inst.get_pins("clk") +
                           self.data_in_flops_inst.get_pins("clk"),
                "precharge_en_bar": [],
                "wordline_en": [],
            }
        return destination_pins

    def add_control_rails(self):
        super().add_control_rails()
        if self.double_control_buffer:
            clk_buf_rail = self.clk_buf_rail
            x_offset = clk_buf_rail.lx() - 2 * self.control_rail_pitch
            self.leftmost_rail = self.add_rect(METAL2, offset=vector(x_offset,
                                                                     clk_buf_rail.by()))

    def route_right_logic_buffer(self):
        """Route logic buffer output pins to the right of the flops"""
        if not self.double_control_buffer:
            super().route_right_logic_buffer()
            return

        x_offset = max(self.mask_in_flops_inst.rx(), self.read_buf_inst.rx()) + 2 * self.wide_m1_space
        # avoid clash with right_vdd
        x_offset = min(x_offset, self.right_vdd.lx() - self.wide_m1_space - 2 * self.m2_pitch)

        y_offset = self.clk_buf_rail.by() + 2 * self.control_rail_pitch

        self.sense_en_rail = self.add_rect("metal2", offset=vector(x_offset, y_offset),
                                           height=self.search_sense_inst.by() - self.rail_height
                                                  - m2m3.height - y_offset)
        x_offset += self.m2_pitch

        bitline_y = y_offset - self.control_rail_pitch

        top_pin = max(self.bitline_logic_array_inst.get_pins("en"), key=lambda x: x.uy())
        self.bitline_en_rail = self.add_rect("metal2", offset=vector(x_offset, bitline_y),
                                             height=top_pin.uy() - bitline_y)

        self.connect_bitline_controls()

        self.connect_logic_buffer_to_pin("sense_amp_en", "sense_en")
        dest_pin = self.search_sense_inst.get_pin("en")
        self.add_rect("metal2", offset=self.sense_en_rail.ul(), width=dest_pin.lx() - self.sense_en_rail.lx())
        if self.sense_en_rail.rx() > dest_pin.lx():
            self.add_rect("metal2", offset=self.sense_en_rail.ur(), width=dest_pin.lx() - self.sense_en_rail.rx())
        else:
            self.add_rect("metal2", offset=self.sense_en_rail.ul(), width=dest_pin.lx() - self.sense_en_rail.lx())
        self.add_rect("metal2", offset=vector(dest_pin.lx(), self.sense_en_rail.uy()),
                      height=dest_pin.by() - self.sense_en_rail.uy())

        # create vcomp pin
        self.copy_layout_pin(self.search_sense_inst, "vcomp", "search_ref")

    def route_precharge_to_bitcell_array(self):
        if self.double_control_buffer:
            # precharge rail
            y_offset = self.control_buffers_inst.get_pin("precharge_en_bar").by() - \
                       0.5 * self.rail_height - self.m2_space
            y_offset -= self.control_rail_pitch
            x_offset = self.clk_buf_rail.lx() - self.control_rail_pitch
            offset = vector(x_offset, y_offset)
            precharge_bar_pin = self.control_buffers_inst.get_pin("precharge_en_bar")
            self.add_rect(METAL3, offset=offset, width=precharge_bar_pin.lx() - x_offset)
            self.add_rect(METAL2, offset=vector(precharge_bar_pin.lx(), y_offset),
                          height=precharge_bar_pin.by() - y_offset)
            self.add_contact(m2m3.layer_stack, offset=vector(precharge_bar_pin.lx(), y_offset),
                             rotate=90)
            self.precharge_en_bar_rail = self.add_rect(METAL2, offset=offset,
                                                       height=self.wordline_driver_inst.by() -
                                                              y_offset)

        super().route_precharge_to_bitcell_array()

    def create_wordline_driver(self):
        pass

    def route_wordline_in(self):
        pass

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

    def route_wordline_gnd(self):
        for pin in self.wordline_driver_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=pin.lr(),
                          width=self.mid_gnd.cx() - pin.rx(), height=pin.height())
            self.add_power_via(pin, self.mid_gnd, via_rotate=90)

    def connect_matchlines(self):
        for row in range(self.num_rows):
            # join matchlines
            precharge_ml = self.ml_precharge_array_inst.get_pin("ml[{}]".format(row))
            bitcell_ml = self.bitcell_array_inst.get_pin("ml[{}]".format(row))
            self.add_rect("metal1", offset=vector(precharge_ml.rx(), bitcell_ml.by()),
                          width=bitcell_ml.lx() - precharge_ml.rx(), height=bitcell_ml.height())
            if bitcell_ml.by() > precharge_ml.uy() - self.m1_width:
                y_offset = precharge_ml.by()
                self.add_rect(METAL1, offset=vector(precharge_ml.rx(), y_offset),
                              height=bitcell_ml.uy() - y_offset)
            elif bitcell_ml.uy() < precharge_ml.by() + self.m1_width:
                y_offset = bitcell_ml.by()
                self.add_rect(METAL1, offset=vector(precharge_ml.rx(), y_offset),
                              height=precharge_ml.uy() - y_offset)

    def route_wordline_driver(self):
        # connect wordline en to rail
        if self.double_control_buffer:
            # precharge rail
            y_offset = self.precharge_en_bar_rail.by() - self.control_rail_pitch
            x_offset = self.precharge_en_bar_rail.lx() - self.control_rail_pitch
            offset = vector(x_offset, y_offset)
            wordline_en_pin = self.control_buffers_inst.get_pin("wordline_en")
            self.add_rect(METAL3, offset=offset, width=wordline_en_pin.lx() - x_offset)
            self.add_rect(METAL2, offset=vector(wordline_en_pin.lx(), y_offset),
                          height=wordline_en_pin.by() - y_offset)
            self.add_contact(m2m3.layer_stack, offset=vector(wordline_en_pin.lx(), y_offset),
                             rotate=90)
            self.wordline_en_rail = self.add_rect(METAL2, offset=offset,
                                                  height=self.wordline_driver_inst.by() -
                                                         y_offset)
        en_rail = getattr(self, "wordline_en_rail")
        en_pin = self.wordline_driver_inst.get_pin("en")

        self.add_contact(m2m3.layer_stack, offset=en_rail.ll())

        y_offset = en_pin.by() - self.wide_m1_space - self.m3_width
        self.add_rect("metal2", offset=vector(en_pin.lx(), y_offset), height=en_pin.by() - y_offset)
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), width=en_rail.rx() - en_pin.lx())
        self.add_rect("metal2", offset=en_rail.ul(), height=y_offset - en_rail.uy())
        self.add_contact(m2m3.layer_stack, offset=vector(en_pin.lx(), y_offset))
        self.add_contact(m2m3.layer_stack, offset=vector(en_rail.lx(), y_offset - m2m3.height + self.m3_width))

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
                                                  via_y + 0.5 * (m2m3.height - self.m3_width)),
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

            y_offset = via_offset.y + 0.5 * (m2m3.height - self.m1_width)
            self.add_rect(METAL1, offset=vector(x_offset, y_offset),
                          width=bitcell_pin.lx() - x_offset + self.m1_width)
            self.add_rect(METAL1, offset=vector(bitcell_pin.lx(), y_offset), width=self.m1_width,
                          height=bitcell_pin.cy() - y_offset)

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
