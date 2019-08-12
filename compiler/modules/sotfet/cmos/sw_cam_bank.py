from base import utils
from base.contact import m2m3, m3m4, m1m2, contact
from base.vector import vector
from globals import OPTS
from modules.sotfet.cmos.sw_logic_buffers import SwLogicBuffers
from modules.sotfet.sf_cam_bank import SfCamBank
from tech import drc


class SwCamBank(SfCamBank):

    write_driver_array = sl_driver_array = None
    write_driver_array_inst = sl_driver_array_inst = None

    @staticmethod
    def get_module_list():
        return SfCamBank.get_module_list() + ["write_driver_array", "sl_driver_array"]

    def add_wordline_pins(self):
        pass

    def add_bitline_logic(self):
        self.add_sl_driver_array()
        self.add_write_driver_array()

    def get_data_flops_offset(self):
        return self.write_driver_array_inst.ll() - vector(0, self.msf_data_in.height)

    def get_mask_flops_offset(self):
        clk_pin = self.msf_data_in.ms.get_pin("clk")
        top_gnd = max(self.msf_data_in.ms.get_pins("gnd"), key=lambda x: x.uy())
        clk_extension = clk_pin.by()
        gnd_extension = top_gnd.uy() - self.msf_data_in.ms.height

        y_space = -clk_extension + gnd_extension + self.parallel_line_space

        return self.data_in_flops_inst.ll() - vector(0, self.msf_data_in.height+y_space)

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        self.bitcell_array_inst = self.add_inst(name="bitcell_array", mod=self.bitcell_array, offset=vector(0, 0))
        connections = []
        for i in range(self.num_cols):
            connections.append("bl[{0}]".format(i))
            connections.append("br[{0}]".format(i))
            connections.append("sl[{0}]".format(i))
            connections.append("slb[{0}]".format(i))
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
                                                                self.wordline_driver.width, 0))

        temp = []
        for i in range(self.num_rows):
            temp.append("dec_out[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("wl[{0}]".format(i))
        temp.append(self.prefix + "wordline_en")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def add_write_driver_array(self):
        offset = vector(0, self.sl_driver_array_inst.by() - self.write_driver_array.height)
        self.write_driver_array_inst = self.add_inst("write_driver_array", mod=self.write_driver_array,
                                                     offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("data_in[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("bl[{0}]".format(i))
            connections.append("br[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("mask_in[{}]".format(i))
        connections.extend([self.prefix + "wordline_en", "vdd", "gnd"])
        self.connect_inst(connections)

    def add_sl_driver_array(self):
        nimplants_body_tap = self.get_gds_layer_shapes(self.bitcell_array.body_tap, "nimplant")
        top_body_tap_implant = max(nimplants_body_tap, key=lambda x:x[1][1])
        nimplant_extension = top_body_tap_implant[1][1] - self.bitcell.height

        nimplant_drivers = self.get_gds_layer_shapes(self.sl_driver_array.driver, "nimplant")
        top_nimplant = max(nimplant_drivers, key=lambda x: x[1][1])
        driver_extension = top_nimplant[1][1] - self.sl_driver_array.driver.height

        y_space = nimplant_extension + driver_extension + drc["parallel_implant_to_implant"]

        offset = self.bitcell_array_inst.ll() - vector(0, y_space + self.sl_driver_array.height)
        self.sl_driver_array_inst = self.add_inst("sl_driver_array", mod=self.sl_driver_array,
                                                  offset=offset)
        connections = []
        for i in range(self.num_cols):
            connections.append("data_in[{0}]".format(i))
            connections.append("sl[{0}]".format(i))
            connections.append("slb[{0}]".format(i))
            connections.append("mask_in[{0}]".format(i))
        connections.append(self.prefix + "sense_amp_en")
        connections.append("vdd")
        connections.append("gnd")

        self.connect_inst(connections)

        # fill implant space between bitcells and driver
        pimplants_bitcell = self.get_gds_layer_shapes(self.bitcell, "pimplant")
        top_bitcell_implant = max(pimplants_bitcell, key=lambda x: x[1][1])
        pimplant_extension = top_bitcell_implant[1][1] - self.bitcell.height

        pimplant_drivers = self.get_gds_layer_shapes(self.sl_driver_array.driver, "pimplant")
        top_pimplant = max(pimplant_drivers, key=lambda x: x[1][1])
        driver_extension = top_pimplant[1][1] - self.sl_driver_array.driver.height

        height = y_space - pimplant_extension - driver_extension
        y_offset = self.sl_driver_array_inst.uy() + driver_extension
        x_extension = top_pimplant[0][0]
        x_offset = self.bitcell_array.body_tap.width + x_extension
        width = self.sl_driver_array_inst.rx() - x_offset - x_extension
        self.add_rect("pimplant", offset=vector(x_offset, y_offset), height=height, width=width)

    def create_bitline_logic(self):
        self.write_driver_array = self.create_module("write_driver_array", columns=self.num_cols,
                                                     word_size=self.word_size)
        self.add_mod(self.write_driver_array)
        self.sl_driver_array = self.create_module("sl_driver_array", columns=self.num_cols,
                                                  word_size=self.word_size)
        self.add_mod(self.sl_driver_array)

        self.logic_buffers = SwLogicBuffers()
        self.add_mod(self.logic_buffers)

    def create_wordline_driver(self):
        self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows,
                                                  buffer_stages=OPTS.wordline_buffers)

    def add_logic_buffers(self):
        offset = vector(self.logic_buffers_x + self.logic_buffers.width, self.logic_buffers_bottom)
        self.logic_buffers_inst = self.add_inst("logic_buffers", mod=self.logic_buffers, offset=offset, mirror="MY")
        connections = ["bank_sel", "clk", "search"]
        connections.extend([self.prefix + x for x in ["clk_buf", "clk_bar", "sense_amp_en", "wordline_en",
                                                      "matchline_chb"]])
        connections.extend(["vdd", "gnd"])
        self.connect_inst(connections)

        self.min_point = min(self.logic_buffers_inst.by() - self.m3_pitch,
                             self.row_decoder_inst.by() - 0.5 * self.rail_height)

    def get_right_gnd_offset(self):
        body_tap_width = self.bitcell_array.body_tap.width
        # need m3 -> m2 -> m1 via for ml
        return body_tap_width - self.wide_m1_space - self.vdd_rail_width - self.m2_width - self.m2_space

    def get_num_left_rails(self):
        # ml_chb, wordline_en, 2 will be below decoder
        return self.num_address_bits - self.address_flops_vert + 2

    def get_num_horizontal_rails(self):
        # add one extra for space to flops din pin
        left_vertical_rails = ["ml_chb", "wordline_en"]
        return self.num_address_bits + len(left_vertical_rails) + 1

    def add_left_right_rails(self, rail_x, rail_y):
        top_y = -self.line_end_space - m2m3.second_layer_height

        # ml_chb, wordline_en
        for rail_name in ["wordline_en", "ml_chb"]:
            rect = self.add_rect("metal2", offset=vector(rail_x, rail_y), height=top_y - rail_y)
            setattr(self, rail_name + "_rail", rect)
            rail_y += self.m3_pitch
            rail_x += self.m2_pitch

        # right rails
        rail_y = self.address_flops[-1].get_pin("vdd").uy()
        rail_x = self.right_rail_x

        rail_names = ["clk_buf", "sense_en"]
        top_clk = max(self.data_in_flops_inst.get_pins("clk"), key=lambda x: x.uy())

        rail_tops = [top_clk.uy(), top_y]
        rail_y += 2 * self.m3_pitch
        for i in range(len(rail_names)):
            rail_name = rail_names[i]
            rect = self.add_rect("metal2", offset=vector(rail_x, rail_y), height=rail_tops[i] - rail_y)
            setattr(self, rail_name + "_rail", rect)
            rail_y -= self.m3_pitch
            rail_x += self.m2_pitch

    def add_bitline_buffers(self):
        pass

    def connect_matchlines(self):
        for row in range(self.num_rows):
            # join matchlines
            precharge_ml = self.ml_precharge_array_inst.get_pin("ml[{}]".format(row))
            bitcell_ml = self.bitcell_array_inst.get_pin("ml[{}]".format(row))\



            x_offset = bitcell_ml.lx() - self.m2_space - self.m2_width
            y_offset = bitcell_ml.uy() - m1m2.second_layer_height if row % 2 == 1 else bitcell_ml.by()
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset, y_offset))
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, y_offset))

            x_offset2 = precharge_ml.rx() + self.parallel_line_space + self.m1_width
            if row % 2 == 0:
                self.add_rect("metal1", offset=precharge_ml.lr(), width=x_offset2 - precharge_ml.rx())
                self.add_rect("metal1", offset=vector(x_offset2, precharge_ml.by()),
                              height=bitcell_ml.uy() - precharge_ml.by())
                self.add_rect("metal1", offset=vector(x_offset2, y_offset), width=x_offset-x_offset2)
            else:
                self.add_rect("metal1", offset=precharge_ml.lr(), width=x_offset2 - precharge_ml.rx())
                self.add_rect("metal1", offset=vector(x_offset2, y_offset),
                              height=precharge_ml.uy() - y_offset)
                self.add_rect("metal1", offset=vector(x_offset2, y_offset), width=x_offset - x_offset2)

            self.add_rect("metal3", offset=vector(x_offset, bitcell_ml.by()), width=bitcell_ml.lx()-x_offset)
            m2_fill_height = utils.ceil(self.minarea_metal1_minwidth/self.m2_width)
            y_offset = bitcell_ml.uy() - m2_fill_height if row % 2 == 0 else bitcell_ml.by()
            self.add_rect("metal2", offset=vector(x_offset, y_offset), height=m2_fill_height)

            # bitcell ml to sense_amp
            sense_amp_ml = self.search_sense_inst.get_pin("ml[{}]".format(row))
            if row % 2 == 0:
                self.add_rect("metal3", offset=vector(sense_amp_ml.ll()), height=bitcell_ml.uy()-sense_amp_ml.by())
            else:
                self.add_rect("metal3", offset=bitcell_ml.lr(), height=sense_amp_ml.uy()-bitcell_ml.by())

    def get_closest_logic_buffer_inverter(self):
        buffer_offset = self.logic_buffers.wordline_buf_inst.by()
        buffer_inverter = self.logic_buffers.wordline_buf.module_insts[-1].mod
        return buffer_offset, buffer_inverter

    def route_wordline_driver(self):
        # connect wordline en to rail
        en_rail = getattr(self, "wordline_en_rail")
        en_pin = self.wordline_driver_inst.get_pin("en")

        y_offset = en_rail.uy() - self.m3_width
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), height=en_pin.by()-y_offset)
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), width=en_rail.lx()-en_pin.lx())
        self.add_contact(m2m3.layer_stack, offset=vector(en_rail.lx(), en_rail.uy()-m2m3.second_layer_height))
        self.add_contact(m2m3.layer_stack, offset=en_pin.ll())

        # connect buffer wordline output to rail
        buffer_pin = self.logic_buffers_inst.get_pin("wordline_en")
        self.add_rect("metal2", offset=buffer_pin.ul(), height=en_rail.by() - buffer_pin.uy())
        self.add_rect("metal3", offset=en_rail.ll(), width=buffer_pin.lx() - en_rail.lx())
        self.add_contact(m2m3.layer_stack,
                         offset=vector(buffer_pin.lx() + 0.5 * self.m2_width + 0.5 * m2m3.first_layer_height,
                                       en_rail.by()), rotate=90)
        self.add_contact(m2m3.layer_stack, offset=en_rail.ll())

        # route wl pin
        via_x = self.left_vdd.lx() - self.parallel_line_space - self.m2_width
        fill_height = utils.ceil(self.minarea_metal1_minwidth/self.m2_width)

        decoder_via_x = self.wordline_driver_inst.get_pin("en").rx() + self.line_end_space + m1m2.first_layer_height

        for row in range(self.num_rows):
            driver_pin = self.wordline_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_pin = self.bitcell_array_inst.get_pin("wl[{}]".format(row))

            self.add_contact_center(m2m3.layer_stack, offset=driver_pin.center())
            self.add_rect_center("metal2", offset=driver_pin.center(), height=fill_height)
            self.add_rect("metal3", offset=driver_pin.ll(), width=via_x-driver_pin.lx())

            offset = vector(via_x-0.5*self.m2_width, driver_pin.cy())
            self.add_contact_center(m2m3.layer_stack, offset=offset)
            self.add_contact_center(m1m2.layer_stack, offset=offset)
            self.add_rect_center("metal2", offset=offset, height=fill_height)

            self.add_path("metal1", [offset, bitcell_pin.lc()])

            # route decoder output
            decoder_pin = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            driver_in_pin = self.wordline_driver_inst.get_pin("in[{}]".format(row))
            self.add_rect("metal1", offset=decoder_pin.ll(), width=decoder_via_x-decoder_pin.lx())
            via_y = decoder_pin.by() + 0.5*self.m2_width
            self.add_contact_center(m1m2.layer_stack, offset=vector(decoder_via_x+0.5*self.m2_width, via_y),
                                    rotate=90)
            self.add_path("metal2", [vector(decoder_via_x+0.5*m1m2.second_layer_height, via_y), driver_in_pin.center()])
            self.add_contact_center(m1m2.layer_stack, offset=driver_in_pin.center())


    def connect_bitline_controls(self):
        self.route_write_sl_driver_inputs()

        self.connect_logic_buffer_to_pin("sense_amp_en", "sense_en", self.sl_driver_array_inst.get_pin("en"))
        en_pin = self.sl_driver_array_inst.get_pin("en")
        en_rail = getattr(self, "sense_en_rail")
        self.add_rect("metal2", offset=en_pin.lr(), width=en_rail.lx() - en_pin.rx())

        # connect write driver enable
        wl_rail = getattr(self, "wordline_en_rail")
        en_pin = self.write_driver_array_inst.get_pin("en")
        self.add_rect("metal3", offset=vector(wl_rail.lx(), en_pin.by()), width=en_pin.lx()-wl_rail.lx())
        self.add_contact(m2m3.layer_stack, offset=en_pin.lc()+vector(0, -0.5*m2m3.second_layer_height))
        self.add_contact(m2m3.layer_stack, offset=vector(wl_rail.lx(), en_pin.cy()-0.5*m2m3.second_layer_height))

        # connect sl driver to bitcells
        for col in range(self.num_cols):
            for pin_name in ["sl[{}]".format(col), "slb[{}]".format(col)]:
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name)
                driver_pin = self.sl_driver_array_inst.get_pin(pin_name)
                self.add_rect(bitcell_pin.layer, offset=driver_pin.ul(), height=bitcell_pin.by()-driver_pin.uy(),
                              width=bitcell_pin.width())

        # connect write driver bl, br to bitcells
        y_offset = self.sl_driver_array_inst.get_pin("sl[0]").uy()

        for col in range(self.num_cols):
            for pin_name in ["bl[{}]".format(col), "br[{}]".format(col)]:
                bitcell_pin = self.bitcell_array_inst.get_pin(pin_name)
                for layer in ["metal2", "metal3"]:
                    self.add_rect(layer, offset=vector(bitcell_pin.lx(), y_offset),
                                  height=bitcell_pin.by() - y_offset, width=bitcell_pin.width())
                # add m3 fill
                m3_fill_width = drc["minside_metal1_contact"]
                m3_fill_height = utils.ceil(self.minarea_metal1_contact / m3_fill_width)
                if pin_name.startswith("bl"):
                    x_offset = bitcell_pin.lx()
                else:
                    x_offset = bitcell_pin.rx() - m3_fill_width
                self.add_rect("metal3", offset=vector(x_offset, bitcell_pin.by()-m3_fill_height),
                              width=m3_fill_width, height=m3_fill_height)

                offset = vector(bitcell_pin.lx(), y_offset)
                self.add_contact(m2m3.layer_stack, offset=offset)
                self.add_contact(m3m4.layer_stack, offset=offset)

                write_driver_pin = self.write_driver_array_inst.get_pin(pin_name)
                self.add_rect("metal4", offset=write_driver_pin.ul(), height=bitcell_pin.by()-write_driver_pin.uy())


    def get_collisions(self):
        write_en = self.write_driver_array_inst.get_pin("en")
        return super().get_collisions() + [(write_en.by(), write_en.uy())]

    def get_right_vdd_modules(self):
        write_vdds = self.write_driver_array_inst.get_pins("vdd")
        for pin in write_vdds:
            self.add_rect("metal1", offset=vector(self.left_vdd.lx(), pin.by()),
                          width=pin.lx()-self.left_vdd.lx(), height=pin.height())
        # connect bitcell vdds
        for pin in self.bitcell_array_inst.get_pins("vdd"):
            self.add_rect("metal1", offset=vector(self.left_vdd.lx(), pin.by()), width=pin.lx()-self.left_vdd.lx(),
                          height=pin.height())

        return [self.search_sense_inst, self.logic_buffers_inst,
                self.sl_driver_array_inst, self.mask_in_flops_inst, self.data_in_flops_inst]

    def route_bitline_logic_gnd(self):
        self.route_bitcells_gnd()
        dummy_contact = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in [self.sl_driver_array_inst, self.write_driver_array_inst, self.data_in_flops_inst,
                         self.address_flops[self.address_flops_vert]]:
            gnd_pins = instance.get_pins("gnd")
            for pin in gnd_pins:
                self.add_rect("metal1", offset=vector(self.right_gnd.lx(), pin.by()),
                              width=pin.lx() - self.right_gnd.lx(), height=pin.height())
                self.add_contact(m1m2.layer_stack,
                                 offset=vector(self.right_gnd.lx() + dummy_contact.second_layer_height, pin.by()),
                                 size=[2, 1], rotate=90)
        for gnd_pin in self.mask_in_flops_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=vector(self.right_gnd.lx(), gnd_pin.by()),
                          width=gnd_pin.lx() - self.right_gnd.lx(), height=gnd_pin.height())
            self.add_contact(m1m2.layer_stack,
                             offset=vector(self.right_gnd.lx() + dummy_contact.second_layer_height, gnd_pin.uy()
                                           - dummy_contact.second_layer_width),
                             size=[2, 1], rotate=90)

    def route_bitcells_gnd(self):
        # connect bitcell gnds
        for pin in self.bitcell_array_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=vector(self.right_gnd.lx(), pin.by()), width=pin.lx() - self.right_gnd.lx(),
                          height=pin.height())
            self.add_contact_center(m1m2.layer_stack, offset=vector(0.5*(self.right_gnd.lx() + self.right_gnd.rx()),
                                                                    pin.cy()), size=[2, 1])

        # sense amp gnd
        sense_amp = self.search_sense_amp_array.amp
        sense_amp_gnd = sense_amp.get_pin("gnd")
        bitcell_gnd = self.bitcell.get_pin("gnd")
        space_to_gnd = bitcell_gnd.by()
        x_offset = self.search_sense_inst.lx() - self.m1_width

        for i in range(1, self.num_rows, 2):
            y_offset = i*sense_amp.height
            self.add_rect("metal1", offset=vector(x_offset, y_offset-space_to_gnd),
                          height=2*space_to_gnd)

    def route_write_sl_driver_inputs(self):
        """
        Connect data flip flop outputs to write driver data pin and mask flip flop outputs to write driver mask pin
        """

        for i in range(self.word_size):
            # route data
            data_flop_out = self.data_in_flops_inst.get_pin("dout[{0}]".format(i))
            data_in_pin = self.write_driver_array_inst.get_pin("data[{}]".format(i))

            self.add_rect("metal4", offset=vector(data_flop_out.lx(), data_in_pin.by()-self.m4_width),
                          width=data_in_pin.rx()-data_flop_out.lx())
            self.add_rect("metal4", offset=data_flop_out.ul(), height=data_in_pin.by()-data_flop_out.uy())
            offset = data_flop_out.ul()-vector(0, m2m3.second_layer_height)
            self.add_contact(m2m3.layer_stack, offset=offset)
            self.add_contact(m3m4.layer_stack, offset=offset)
            m3_fill_height = utils.ceil(self.minarea_metal1_minwidth/self.m3_width)
            self.add_rect("metal3", offset=vector(data_flop_out.lx(), data_flop_out.uy()-m3_fill_height),
                          height=m3_fill_height)

            # route mask
            mask_in_pin = next(filter(lambda pin: pin.layer == "metal3",
                                         self.write_driver_array_inst.get_pins("mask[{}]".format(i))))
            mask_flop_out = self.mask_in_flops_inst.get_pin("dout[{0}]".format(i))
            self.add_contact(m2m3.layer_stack, offset=vector(mask_flop_out.ul()-vector(0, m2m3.second_layer_height)))
            offset = vector(mask_in_pin.lx(), mask_flop_out.uy()-0.5*(m2m3.second_layer_height-self.m3_width))
            self.add_rect("metal3", offset=offset, width=mask_flop_out.rx()-offset.x)
            self.add_rect("metal3", offset=offset, height=mask_in_pin.by()-offset.y)
