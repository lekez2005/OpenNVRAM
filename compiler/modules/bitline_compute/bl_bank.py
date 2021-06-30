from base import utils
from base.contact import m2m3, m1m2, m3m4
from base.vector import vector
from base.well_implant_fills import get_default_fill_layers
from globals import OPTS
from modules.bitline_compute.bl_control_buffers_bank_mixin import BlControlBuffersRepeatersMixin
from modules.bitline_compute.decoder_logic import DecoderLogic
from modules.internal_decoder_bank import InternalDecoderBank
from tech import drc


class BlBank(BlControlBuffersRepeatersMixin, InternalDecoderBank):
    """
    Represents a bitline compute bank
    Each bank includes regular sram modules except sense amp, decoder
    """

    def calculate_dimensions(self):
        self.width = self.bitcell_array_inst.rx() - self.left_decoder_inst.lx()
        self.height = self.left_decoder_inst.uy() - min(self.left_decoder_inst.by(), self.control_buffers_inst.by())

    def add_modules(self):

        self.add_control_flops()
        self.add_control_buffers()

        self.add_read_flop()

        self.add_data_flops()
        self.add_write_driver_array()
        self.add_sense_amp_array()
        self.add_precharge_array()
        self.add_bitcell_array()

        self.add_control_rails()

        self.add_wordline_driver()
        self.add_row_decoder()

        self.add_vdd_gnd_rails()

        self.add_decoder_logic()
        self.add_left_row_decoder()

    def route_layout(self):
        self.route_control_buffer()
        self.route_read_buf()
        self.route_precharge()
        self.route_sense_amp()
        self.route_bitcell()
        self.route_write_driver()
        self.route_flops()
        self.route_wordline_driver()

        self.route_decoder()

        self.route_left_decoder()
        self.route_left_decoder_power()
        self.join_left_decoder_nwell()
        self.route_decoder_enables()

        self.route_wordline_in()

        self.route_compute_pins()
        self.connect_buffer_rails()

        self.calculate_rail_vias()  # horizontal rail vias
        self.add_decoder_power_vias()
        self.add_right_rails_vias()

        self.route_body_tap_supplies()
        self.route_control_buffers_power()

    def create_modules(self):
        super().create_modules()
        self.decoder_logic_mod = DecoderLogic(num_rows=self.num_rows)
        self.add_mod(self.decoder_logic_mod)

    def get_body_taps_bottom(self):
        return self.data_in_flops_inst.by()

    @staticmethod
    def get_module_list():
        return ["bitcell", "bitcell_array", "ms_flop_array", "precharge_array", "write_driver_array",
                "wordline_driver", "decoder", "tri_gate_array", "sense_amp_array"]

    def add_pins(self):
        """ Adding pins for Bank module"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("mask_in_bar[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))
            self.add_pin("ADDR_1[{0}]".format(i))

        self.add_pin_list(["dec_en_0", "dec_en_1", "sense_amp_ref"])

        if self.mirror_sense_amp:
            for pin in ["bank_sel", "read", "clk", "clk_buf", "vdd", "gnd"]:
                self.add_pin(pin)
        else:
            for pin in ["bank_sel", "read", "clk", "sense_trig", "diff", "diffb", "clk_buf", "vdd", "gnd"]:
                self.add_pin(pin)

        for col in range(self.num_cols):
            self.add_pin("and[{}]".format(col))
            self.add_pin("nor[{}]".format(col))

        if OPTS.separate_vdd:
            self.add_pin_list(self.external_vdds)

        if self.mirror_sense_amp and OPTS.sense_trigger_delay > 0:
            self.add_pin("sense_trig")

    def get_enable_names(self):
        return ["en_0", "en_1"]

    def get_right_vdd_offset(self):
        return max(self.control_buffers_inst.rx(), self.bitcell_array_inst.rx(),
                   self.read_buf_inst.rx()) + self.wide_m1_space + self.m4_width + self.wide_m1_space

    def get_collisions(self):
        return [
            (self.bottom_en_rail.by(), self.data_in_flops_inst.uy() + 2*(self.m4_width + self.line_end_space)
             + self.line_end_space),

            (self.sense_amp_array_inst.by() - m3m4.second_layer_height - self.line_end_space,
             self.sense_amp_array_inst.uy()),
            (self.en_0_buf_inst.by() - 2*self.control_rail_pitch,
             self.en_0_buf_inst.by()),
            (self.decoder_clk_rail.by(), self.decoder_clk_rail.uy()),
        ]

    def add_control_buffers(self):
        offset = vector(self.en_0_buf_inst.rx() + self.poly_pitch + self.control_buffers.width,
                        self.logic_buffers_bottom)
        self.control_buffers_inst = self.add_inst("control_buffers", mod=self.control_buffers,
                                                  offset=offset, mirror="MY")
        self.connect_control_buffers()

        # fill implants between en_0 and logic_buffers
        flop = self.control_flop.flop
        control_inverter = self.control_buffers.sense_amp_buf.buffer_mod.buffer_invs[-1]

        flop_y_offset = self.en_0_buf_inst.by() + self.control_flop.flop_inst.by()
        flop_x_offset = self.en_0_buf_inst.rx() - self.control_flop.flop_inst.lx()

        control_y_offset = self.control_buffers_inst.by() + self.control_buffers.sense_amp_buf_inst.by()
        control_x_offset = (self.control_buffers_inst.lx() +
                            (self.control_buffers.width -
                             self.control_buffers.sense_amp_buf_inst.lx() -
                             self.control_buffers.sense_amp_buf.buffer_inst.lx() -
                             self.control_buffers.sense_amp_buf.buffer_mod.module_insts[-1].lx()))

        for layer, purpose in get_default_fill_layers():
            flop_rects = flop.get_gds_layer_rects(layer, purpose)

            flop_rect = max(filter(lambda x: x.lx() <= 0.25 * flop.width, flop_rects),
                            key=lambda x: x.height)

            control_rects = control_inverter.get_layer_shapes(layer, purpose)
            control_rect = self.rightmost_largest_rect(control_rects)

            bottom = max(flop_rect.by() + flop_y_offset, control_rect.by()+control_y_offset)
            top = max(flop_rect.uy() + flop_y_offset, control_rect.uy()+control_y_offset)

            left = flop_x_offset - flop_rect.lx()
            right = control_x_offset - control_rect.rx()
            self.add_rect(layer, offset=vector(left, bottom), width=right-left, height=top-bottom)

            # connect bottom pimplants
            if layer == "pimplant":

                bottom_y = min(flop_rects, key=lambda x: x.by()).by()
                bottom_left_flop = min(filter(lambda x: x.by() == bottom_y, flop_rects), key=lambda x: x.lx())

                bottom_y = min(control_rects, key=lambda x: x.by()).by()
                bottom_right_control = max(filter(lambda x: x.by() == bottom_y, control_rects), key=lambda x: x.rx())

                top = min(bottom_right_control.uy() + control_y_offset, bottom_left_flop.uy() + flop_y_offset)

                bottom = top - max(bottom_right_control.height, bottom_left_flop.height)

                left = flop_x_offset - bottom_left_flop.lx() - self.implant_width
                right = control_x_offset - bottom_right_control.rx() + self.implant_width

                width = right-left
                self.add_rect(layer, offset=vector(left, bottom), width=width, height=top - bottom)
            elif layer == "nimplant":  # connect top nimplants
                top_y = max(flop_rects, key=lambda x: x.uy()).uy()
                top_left_flop = min(filter(lambda x: x.uy() == top_y, flop_rects), key=lambda x: x.lx())

                top_y = max(control_rects, key=lambda x: x.uy()).uy()
                top_right_control = max(filter(lambda x: x.uy() == top_y, control_rects), key=lambda x: x.rx())

                bottom = top_left_flop.by() + flop_y_offset
                top = top_left_flop.uy() + flop_y_offset

                left = flop_x_offset - top_left_flop.lx()
                right = control_x_offset - top_right_control.rx()
                self.add_rect(layer, offset=vector(left, bottom), width=right - left, height=top - bottom)

    def add_data_flops(self):
        data_connections = []
        vdd_name = "vdd_data_flops" if OPTS.separate_vdd else "vdd"
        for i in range(self.word_size):
            data_connections.append("DATA[{}]".format(i))
        for i in range(self.word_size):
            data_connections.extend("data_in[{0}] data_in_bar[{0}]".format(i).split())
        data_connections.extend(["clk_bar", vdd_name, "gnd"])

        y_offset = self.trigate_y
        self.data_in_flops_inst = self.add_inst("data_in", mod=self.msf_data_in, offset=vector(0, y_offset))
        self.connect_inst(data_connections)

    def add_sense_amp_array(self):
        """ Adding Sense amp  """
        self.sense_amp_array_offset = self.write_driver_array_inst.ul()
        self.sense_amp_array_inst = self.add_inst(name="sense_amp_array", mod=self.sense_amp_array,
                                                  offset=self.sense_amp_array_offset)
        temp = []
        for i in range(self.word_size):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))

            temp.append("and[{0}]".format(i))
            temp.append("nor[{0}]".format(i))

        if self.mirror_sense_amp:
            temp.extend(["sense_en", "sense_en_bar", "sense_amp_ref", "vdd", "gnd"])
        else:
            temp.extend(["sense_en", "sense_precharge_bar", "sample_en_bar",
                         "diff", "diffb", "sense_amp_ref", "vdd", "gnd"])
        self.connect_inst(temp)

    def get_wordline_in_net(self):
        return "wl_in[{}]"

    def get_control_rails_destinations(self):
        if self.mirror_sense_amp:
            destination_pins = {
                "sense_en": self.sense_amp_array_inst.get_pins("en"),
                "sense_en_bar": self.sense_amp_array_inst.get_pins("en_bar"),
                "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
                "clk_bar": self.data_in_flops_inst.get_pins("clk"),
                "clk_buf": [],
                "write_en": self.write_driver_array_inst.get_pins("en"),
                "write_en_bar": self.write_driver_array_inst.get_pins("en_bar"),
                "wordline_en": self.precharge_array_inst.get_pins("en"),
            }
        else:
            destination_pins = {
                "sense_en": self.sense_amp_array_inst.get_pins("en"),
                # "sense_en_bar": self.sense_amp_array_inst.get_pins("en_bar"),
                "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
                "sample_en_bar": self.sense_amp_array_inst.get_pins("sampleb"),
                "clk_bar": self.data_in_flops_inst.get_pins("clk"),
                "clk_buf": [],
                "write_en": self.write_driver_array_inst.get_pins("en"),
                "write_en_bar": self.write_driver_array_inst.get_pins("en_bar"),
                "wordline_en": self.precharge_array_inst.get_pins("en"),
            }
        return destination_pins

    def add_decoder_logic(self):
        x_offset = self.left_gnd.lx() - self.wide_m1_space - self.decoder_logic_mod.width
        self.decoder_logic_inst = self.add_inst(self.decoder_logic_mod.name, mod=self.decoder_logic_mod,
                                                offset=vector(x_offset, self.bitcell_array_inst.by()))
        nets = []
        for row in range(self.num_rows):
            nets.append('dec_out[{}]'.format(row))
            nets.append('dec_out_1[{}]'.format(row))
            nets.append('wl_in[{}]'.format(row))

        nets.append("dec_en_0_buf")
        nets.append("dec_en_1_buf")
        vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"
        nets.extend([vdd_name, "gnd"])

        self.connect_inst(nets)

    def add_left_row_decoder(self):
        """  Add the hierarchical row decoder  """

        x_offset = min(
            self.left_gnd.lx() - self.wide_m1_space - self.decoder.width,
            self.decoder_logic_inst.lx() - self.decoder.row_decoder_width
        )

        offset = vector(x_offset, self.row_decoder_inst.by())

        self.left_decoder_inst = self.add_inst(name="left_row_decoder", mod=self.decoder, offset=offset)

        temp = []
        for i in range(self.row_addr_size):
            temp.append("ADDR_1[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out_1[{0}]".format(j))
        vdd_name = "vdd_wordline" if OPTS.separate_vdd else "vdd"
        temp.extend(["clk_buf", vdd_name, "gnd"])
        self.connect_inst(temp)

    def add_control_flops(self):

        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"

        x_offset = self.control_flop.width
        y_offset = self.logic_buffers_bottom + self.control_buffers.height - self.control_flop.height
        offset = vector(x_offset, y_offset)

        self.en_1_buf_inst = self.add_inst("en_1_buf", mod=self.control_flop, offset=offset, mirror="MY")

        self.connect_inst(["dec_en_1", "clk_buf", "dec_en_1_buf", vdd_name, "gnd"])

        offset = self.en_1_buf_inst.lr() + vector(self.control_flop.width, 0)
        self.en_0_buf_inst = self.add_inst("en_0_buf", mod=self.control_flop, offset=offset, mirror="MY")

        self.connect_inst(["dec_en_0", "clk_buf", "dec_en_0_buf", vdd_name, "gnd"])

        flop = self.control_flop.flop
        inverter = self.control_flop.buffer.insts[-1].mod

        flop_y_offset = self.en_1_buf_inst.by() + self.control_flop.flop_inst.by()
        flop_x_offset = self.en_1_buf_inst.rx() - self.control_flop.flop_inst.lx()

        inverter_y_offset = (self.en_0_buf_inst.by() + self.control_flop.buffer_inst.by() +
                             self.control_flop.buffer.insts[-1].by())
        inverter_x_offset = (self.en_0_buf_inst.lx() + (self.control_flop.width
                                                        - self.control_flop.buffer_inst.lx() -
                                                        self.control_flop.buffer.insts[-1].lx()))

        layers = ["pimplant", "nimplant"]
        for i in range(2):
            layer = layers[i]
            # fill implants between en_0 and en_1

            flop_rects = flop.get_gds_layer_rects(layer)
            # find left-most and biggest flop rect
            left_x = min([x.lx() for x in flop_rects])
            flop_rect = max(filter(lambda x: x.lx() == left_x, flop_rects), key=lambda x: x.height)
            # find right-most and biggest inverter rect
            inverter_rects = inverter.get_layer_shapes(layer)
            right_x = max([x.rx() for x in inverter_rects])
            inverter_rect = max(filter(lambda x: x.rx() == right_x, inverter_rects), key=lambda x: x.height)

            bottom_y = max(flop_y_offset+flop_rect.by(), inverter_y_offset+inverter_rect.by())
            top_y = max(flop_y_offset+flop_rect.uy(), inverter_y_offset+inverter_rect.uy())

            left_x = flop_x_offset - flop_rect.lx()
            right_x = inverter_x_offset - inverter_rect.rx()

            self.add_rect(layer, offset=vector(left_x, bottom_y), width=right_x-left_x,
                          height=top_y-bottom_y)

    def get_vdd_gnd_rail_layers(self):
        return ["metal2", "metal1", "metal2", "metal2", "metal2", "metal2"]

    def route_control_buffer(self):
        self.copy_layout_pin(self.control_buffers_inst, "bank_sel", "bank_sel")
        self.copy_layout_pin(self.control_buffers_inst, "clk", "clk")
        if not self.mirror_sense_amp or OPTS.sense_trigger_delay > 0:
            self.copy_layout_pin(self.control_buffers_inst, "sense_trig", "sense_trig")

        if OPTS.separate_vdd:
            enable_flop_vdd = self.en_0_buf_inst.get_pin("vdd")
            control_buffers_vdd = self.control_buffers_inst.get_pin("vdd")
            vdd_height = min(enable_flop_vdd.height(), control_buffers_vdd.height())
            y_offset = enable_flop_vdd.cy() - 0.5 * vdd_height
            self.add_layout_pin("vdd_buffers", "metal1", offset=vector(enable_flop_vdd.lx(), y_offset),
                                height=vdd_height, width=control_buffers_vdd.rx()-enable_flop_vdd.lx())
        else:
            self.route_vdd_pin(self.control_buffers_inst.get_pin("vdd"))

        # gnd
        read_flop_gnd = self.read_buf_inst.get_pin("gnd")
        control_buffers_gnd = self.control_buffers_inst.get_pin("gnd")

        # join grounds
        # control_buffers gnd to read gnd
        offset = vector(control_buffers_gnd.rx() - read_flop_gnd.height(), read_flop_gnd.by())
        self.add_rect("metal1", offset=offset, width=read_flop_gnd.lx()-offset.x, height=read_flop_gnd.height())
        self.add_rect("metal1", offset=offset, width=read_flop_gnd.height(),
                      height=control_buffers_gnd.by()-read_flop_gnd.by())

        # control_flops to control_buffers
        en_0_flop_gnd = self.en_0_buf_inst.get_pin("gnd")
        self.add_rect("metal1", offset=en_0_flop_gnd.lr(), width=control_buffers_gnd.lx()-en_0_flop_gnd.rx(),
                      height=en_0_flop_gnd.height())
        self.add_rect("metal1", offset=vector(control_buffers_gnd.lx(), en_0_flop_gnd.by()),
                      width=control_buffers_gnd.height(), height=control_buffers_gnd.by()-en_0_flop_gnd.by())

        # en_1 flop gnd to rail
        en_1_flop_gnd = self.en_1_buf_inst.get_pin("gnd")
        self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), en_1_flop_gnd.by()),
                      width=en_1_flop_gnd.lx() - self.mid_gnd.lx(), height=en_1_flop_gnd.height())
        self.add_power_via(en_1_flop_gnd, self.mid_gnd, via_rotate=90)

        # read flop gnd to rail
        self.add_rect("metal1", offset=read_flop_gnd.lr(), height=read_flop_gnd.height(),
                      width=self.right_gnd.rx()-read_flop_gnd.rx())

    def route_sense_amp(self):
        self.route_sense_amp_common()

        if not self.mirror_sense_amp:
            for pin in self.sense_amp_array_inst.get_pins("gnd"):
                self.route_gnd_pin(pin)

        if self.mirror_sense_amp:
            for pin in self.sense_amp_array_inst.get_pins("vdd"):
                self.route_vdd_pin(pin)
        else:
            vdd_pins = self.sense_amp_array_inst.get_pins("vdd")

            upper_vdd = max(vdd_pins, key=lambda x: x.by())
            lower_vdd = min(vdd_pins, key=lambda x:x.by())

            self.add_rect("metal1", offset=vector(self.mid_vdd.lx(), lower_vdd.by()),
                          width=self.right_vdd.rx() - self.mid_vdd.lx(), height=lower_vdd.height())

            self.add_contact(m1m2.layer_stack, offset=vector(self.right_vdd.lx() + 0.2, lower_vdd.uy()-0.18),
                             size=[2, 1], rotate=90)
            self.add_contact(m1m2.layer_stack, offset=vector(self.mid_vdd.lx() + 0.2, lower_vdd.uy()-0.18),
                             size=[2, 1], rotate=90)

            self.route_vdd_pin(upper_vdd)

        search_ref_pins = self.sense_amp_array_inst.get_pins("search_ref")
        top_pin = max(search_ref_pins, key=lambda x: x.by())
        bot_pin = min(search_ref_pins, key=lambda x: x.by())
        self.add_layout_pin("sense_amp_ref", top_pin.layer, offset=top_pin.ll(), width=top_pin.width(),
                            height=top_pin.height())
        offset = vector(self.bitcell_array_inst.lx() - self.line_end_space, bot_pin.by())
        self.add_rect("metal2", offset=offset, height=top_pin.uy()-bot_pin.by())
        self.add_contact(m2m3.layer_stack, offset=offset+vector(m2m3.second_layer_height, 0), rotate=90)
        self.add_contact(m2m3.layer_stack, offset=vector(offset.x + m2m3.second_layer_height, top_pin.by()),
                         rotate=90)

        if not self.mirror_sense_amp:
            # connect diff and diffb pins
            self.copy_layout_pin(self.sense_amp_array_inst, "diff", "diff")
            self.copy_layout_pin(self.sense_amp_array_inst, "diffb", "diffb")

            diff_pins = self.sense_amp_array_inst.get_pins("diff")
            diffb_pins = self.sense_amp_array_inst.get_pins("diffb")

            all_pins = [diff_pins, diffb_pins]

            base_x = self.mid_gnd.rx() + self.m4_space

            for i in range(2):
                x_offset = base_x + i*(self.m4_width + self.m4_space)
                pins = all_pins[i]
                top_pin = max(pins, key=lambda x: x.by())
                bot_pin = min(pins, key=lambda x: x.by())
                self.add_rect("metal4", offset=vector(x_offset, bot_pin.by()), height=top_pin.uy() - bot_pin.by())
                for pin in pins:
                    self.add_rect("metal3", offset=vector(x_offset, pin.by()), width=pin.lx()-x_offset)
                    if pin == bot_pin:
                        self.add_contact(m3m4.layer_stack, offset=vector(x_offset, pin.by()))
                    else:
                        self.add_contact(m3m4.layer_stack, offset=vector(x_offset, pin.uy()-m3m4.height))

    def route_write_driver(self):
        for col in range(self.num_cols):
            # connect bitline to sense amp
            for pin_name in ["bl", "br"]:
                driver_pin = self.write_driver_array_inst.get_pin(pin_name + "[{}]".format(col))
                sense_amp_pin = self.sense_amp_array_inst.get_pin(pin_name + "[{}]".format(col))
                self.add_contact(m3m4.layer_stack, offset=vector(sense_amp_pin.lx(), driver_pin.uy()-m3m4.height))

            # route data_bar
            flop_pin = self.data_in_flops_inst.get_pin("dout_bar[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data_bar[{}]".format(col))
            self.add_rect("metal2", offset=flop_pin.ul(), height=driver_pin.by()-flop_pin.uy())
            self.add_contact(m2m3.layer_stack, offset=driver_pin.ll()-vector(0, m2m3.second_layer_height))

            # route data
            flop_pin = self.data_in_flops_inst.get_pin("dout[{}]".format(col))
            driver_pin = self.write_driver_array_inst.get_pin("data[{}]".format(col))
            offset = vector(driver_pin.lx(), flop_pin.uy()-self.m2_width)
            self.add_rect("metal2", offset=offset, width=flop_pin.rx()-offset.x)
            self.add_contact(m2m3.layer_stack, offset=offset)
            self.add_rect("metal3", offset=offset, height=driver_pin.by()-offset.y)

        # route power, gnd

        for pin in self.write_driver_array_inst.get_pins("vdd"):
            self.route_vdd_pin(pin, via_rotate=0)
        gnd_pins = self.write_driver_array_inst.get_pins("gnd")
        top_gnd = max(gnd_pins, key=lambda x: x.by())  # bottom pin overlaps flop gnds
        self.route_gnd_pin(top_gnd, via_rotate=0)

    def route_flops(self):
        if OPTS.separate_vdd:
            self.copy_layout_pin(self.data_in_flops_inst, "vdd", "vdd_data_flops")
        else:
            for pin in self.data_in_flops_inst.get_pins("vdd"):
                self.route_vdd_pin(pin)
        # TODO temp via hack
        data_in_gnds = list(sorted(self.data_in_flops_inst.get_pins("gnd"), key=lambda x: x.by()))
        self.route_gnd_pin(data_in_gnds[0], via_rotate=0)
        self.route_gnd_pin(data_in_gnds[1], via_rotate=90)

    def route_left_decoder_power(self):
        # connect vdd
        if OPTS.separate_vdd:
            right_vdd_x = self.left_vdd.lx()
        else:
            right_vdd_x = self.wordline_driver_inst.lx()
        for vdd_pin in self.left_decoder_inst.get_pins("vdd"):
            self.add_rect("metal1", offset=vdd_pin.lr(), width=right_vdd_x - vdd_pin.rx(),
                          height=vdd_pin.height())

        for gnd_pin in self.left_decoder_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=gnd_pin.lr(), width=self.left_gnd.lx()-gnd_pin.rx(),
                          height=gnd_pin.height())

    def route_wordline_in(self):
        # route decoder in
        for row in range(self.num_rows):

            logic_in_0 = self.decoder_logic_inst.get_pin("in_0[{}]".format(row))
            decoder_out_0 = self.row_decoder_inst.get_pin("decode[{}]".format(row))

            logic_in_1 = self.decoder_logic_inst.get_pin("in_1[{}]".format(row))
            decoder_out_1 = self.left_decoder_inst.get_pin("decode[{}]".format(row))

            logic_out = self.decoder_logic_inst.get_pin("out[{}]".format(row))
            wl_in = self.wordline_driver_inst.get_pin("in[{}]".format(row))

            self.add_rect("metal3", offset=logic_in_0.lr(), width=decoder_out_0.rx()-logic_in_0.rx())
            self.add_rect("metal3", offset=vector(decoder_out_1.lx(), logic_in_1.by()),
                          width=logic_in_1.lx()-decoder_out_1.lx())

            if row % 2 == 0:
                # decoder_0 out
                self.add_contact(m2m3.layer_stack,
                                 offset=decoder_out_0.ll() + vector(0, -0.5 * m2m3.second_layer_height))
                self.add_rect("metal3", offset=vector(decoder_out_0.lx(), logic_in_0.by()),
                              height=decoder_out_0.by() - logic_in_0.by())
                # decoder_1 out
                self.add_contact(m2m3.layer_stack,
                                 offset=decoder_out_1.ll() + vector(0, -0.5 * m2m3.second_layer_height))
                self.add_rect("metal3", offset=vector(decoder_out_1.lx(), logic_in_1.by()),
                              height=decoder_out_1.by()-logic_in_1.by())

                # wordline_in
                self.add_contact(m2m3.layer_stack,
                                 offset=logic_out.ul() - vector(0, 0.5 * m2m3.second_layer_height))
                y_offset = (self.decoder_logic_inst.by() + (row+1)*self.bitcell_array.cell.height
                            - 0.5*self.rail_height - self.m3_width)
                self.add_rect("metal3", offset=logic_out.ul(), height=y_offset-logic_out.uy())
                self.add_rect("metal3", offset=vector(logic_out.lx(), y_offset), width=wl_in.rx()-logic_out.lx())
                self.add_rect("metal3", offset=vector(wl_in.lx(), wl_in.cy()), height=y_offset-wl_in.cy())

            else:
                self.add_rect("metal3", offset=decoder_out_0.ul(), height=logic_in_0.uy()-decoder_out_0.uy())
                self.add_contact(m2m3.layer_stack, offset=decoder_out_0.ul() - vector(0, 0.5*m2m3.second_layer_height))

                self.add_rect("metal3", offset=vector(decoder_out_1.lx(), logic_in_1.uy()),
                              height=decoder_out_1.uy() - logic_in_1.uy())
                self.add_contact(m2m3.layer_stack, offset=decoder_out_1.ul() - vector(0, 0.5*m2m3.second_layer_height))

                self.add_contact(m2m3.layer_stack,
                                 offset=logic_out.ll() + vector(0, -0.5 * m2m3.second_layer_height))
                y_offset = self.decoder_logic_inst.by() + row*self.bitcell_array.cell.height + 0.5*self.rail_height
                self.add_rect("metal3", offset=vector(logic_out.lx(), y_offset), height=logic_out.by()-y_offset)
                self.add_rect("metal3", offset=vector(logic_out.lx(), y_offset), width=wl_in.rx() - logic_out.lx())
                self.add_rect("metal3", offset=vector(wl_in.lx(), y_offset), height=wl_in.cy()-y_offset)

            self.add_contact_center(m1m2.layer_stack, wl_in.center())
            self.add_contact_center(m2m3.layer_stack, wl_in.center())
            self.add_rect_center("metal2", offset=wl_in.center(), width=self.fill_width, height=self.fill_height)

    def join_left_decoder_nwell(self):
        decoder_inverter = self.decoder.inv_inst[-1].mod
        logic_nand = self.decoder_logic_mod.nand

        row_decoder_right = self.left_decoder_inst.lx() + self.decoder.row_decoder_width

        layers = ["nwell"]
        purposes = ["drawing"]

        # fill from top-most base to the top of the cell

        for i in range(1):
            decoder_rect = max(decoder_inverter.get_layer_shapes(layers[i], purposes[i]),
                               key=lambda x: x.height)
            logic_rect = max(logic_nand.get_layer_shapes(layers[i], purposes[i]),
                             key=lambda x: x.height)
            top_most = max([decoder_rect, logic_rect], key=lambda x: x.by())
            fill_height = logic_nand.height - top_most.by()
            # extension of rect past top of cell
            rect_y_extension = top_most.uy() - logic_nand.height
            fill_width = self.decoder_logic_inst.lx() - row_decoder_right

            for vdd_pin in self.left_decoder_inst.get_pins("vdd"):
                if utils.round_to_grid(vdd_pin.cy()) == utils.round_to_grid(
                        self.wordline_driver_inst.by()):  # first row
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - rect_y_extension),
                                  width=fill_width, height=top_most.height)
                elif vdd_pin.cy() > self.wordline_driver_inst.by():  # row decoder
                    self.add_rect(layers[i], offset=vector(row_decoder_right, vdd_pin.cy() - fill_height),
                                  width=fill_width, height=2 * fill_height)

    def route_decoder_enables(self):
        # route clk_in to enable flops
        modules = [self.en_0_buf_inst, self.en_1_buf_inst]
        clk_rail = self.clk_buf_rail

        top_y_offset = self.wordline_driver_inst.by() - self.control_rail_pitch
        bottom_y_offset = (min(self.en_1_buf_inst.by() - 0.5*self.rail_height,
                               self.control_buffers_inst.by()) - self.m3_space - self.m3_width)

        self.copy_layout_pin(self.en_0_buf_inst, "din", "dec_en_0")
        self.copy_layout_pin(self.en_1_buf_inst, "din", "dec_en_1")

        x_offset = self.leftmost_rail.lx() - self.control_rail_pitch

        # add rail from clk_buf to clock inputs

        logic_enables = [self.decoder_logic_inst.get_pin("en_0"), self.decoder_logic_inst.get_pin("en_1")]
        flop_enables = [self.en_0_buf_inst.get_pin("dout"), self.en_1_buf_inst.get_pin("dout")]

        for i in range(2):
            # connect clk inputs to clk_buf
            clk_in = modules[i].get_pin("clk")
            self.add_rect("metal2", offset=clk_in.lr(), height=clk_rail.by()-clk_in.by())
            self.add_contact_center(m2m3.layer_stack,
                                    offset=vector(clk_in.rx() + 0.5*self.m2_width,
                                                  clk_rail.by()+0.5*self.m3_width), rotate=90)
            self.add_contact(m1m2.layer_stack, offset=clk_in.lr())

            # connect enable pins

            logic_en = logic_enables[i]
            flop_en = flop_enables[i]

            # bottom horizontal rail
            self.add_rect("metal2", offset=vector(flop_en.lx(), bottom_y_offset),
                          height=flop_en.by()-bottom_y_offset)
            self.add_contact(m2m3.layer_stack, offset=vector(flop_en.lx()+self.m2_width, bottom_y_offset), rotate=90)
            self.bottom_en_rail = self.add_rect("metal3", offset=vector(x_offset, bottom_y_offset),
                                                width=flop_en.lx()-x_offset)

            # vertical rail
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, bottom_y_offset))
            self.add_rect("metal2", offset=vector(x_offset, bottom_y_offset), height=top_y_offset-bottom_y_offset)
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, top_y_offset-m2m3.second_layer_height))

            offset = vector(logic_en.lx(), top_y_offset-self.m3_width)
            # top horizontal rail
            self.add_rect("metal3", offset=offset, width=x_offset-logic_en.lx())
            # to en pin
            self.add_rect("metal2", offset=offset, height=logic_en.by()-top_y_offset + self.m3_width)
            self.add_contact(m2m3.layer_stack, offset=offset)

            x_offset -= self.control_rail_pitch
            top_y_offset -= self.control_rail_pitch
            bottom_y_offset -= self.control_rail_pitch

    def route_left_decoder(self):
        # route clk_buf across right decoder along the closest gnd pin
        clk_rail = self.clk_buf_rail

        target_y = clk_rail.by() + m2m3.second_layer_height
        right_clk_pin = min(self.row_decoder_inst.get_pins("clk"),
                            key=lambda x: min(abs(target_y - x.by()), abs(target_y - x.uy())))

        left_clk_pin = min(self.left_decoder_inst.get_pins("clk"),
                           key=lambda x: abs(x.cy() - right_clk_pin.cy()))

        # find closest vdd-gnd pin to pass clk through to left decoder
        y_offset = clk_rail.by() + m2m3.second_layer_height
        vdd_gnd = self.row_decoder_inst.get_pins("vdd") + self.row_decoder_inst.get_pins("gnd")
        valid_vdd_gnd = filter(lambda x: x.by() > y_offset + self.line_end_space, vdd_gnd)
        closest_vdd_gnd = min(valid_vdd_gnd, key=lambda x: x.by() - y_offset)
        y_offset = closest_vdd_gnd.by()

        self.add_rect("metal3", offset=vector(right_clk_pin.lx(), target_y), height=y_offset - clk_rail.by())

        self.add_rect("metal3", offset=vector(left_clk_pin.lx(), closest_vdd_gnd.cy()-0.5*self.m3_width),
                      width=right_clk_pin.lx()-left_clk_pin.lx())
        y_offset = clk_rail.by() + m2m3.second_layer_height
        self.decoder_clk_rail = self.add_rect("metal3", offset=vector(right_clk_pin.lx(), y_offset),
                                              height=closest_vdd_gnd.cy()+0.5*self.m3_width-y_offset)
        self.add_contact_center(m2m3.layer_stack, offset=vector(left_clk_pin.cx(), closest_vdd_gnd.cy()))

        if closest_vdd_gnd.cy() - 0.5*m2m3.height > left_clk_pin.uy():
            self.add_rect("metal2", offset=left_clk_pin.ul(), height=closest_vdd_gnd.cy()-left_clk_pin.uy())

        # copy address ports
        for i in range(self.addr_size):
            self.copy_layout_pin(self.left_decoder_inst, "A[{}]".format(i), "ADDR_1[{}]".format(i))

    def route_compute_pins(self):
        # get grid locations
        grid_pitch = self.m4_width + self.parallel_line_space
        self.grid_pos = grid_pos = [0.5*self.m4_width + x*grid_pitch for x in range(6)]

        self.copy_layout_pin(self.control_buffers_inst, "clk_buf", "clk_buf")

        pin_bottom = self.bottom_en_rail.by() - m3m4.height - self.line_end_space

        for col in range(self.num_cols):
            # add mask pin

            col_x_start = self.bitcell_array.bitcell_offsets[col] + self.bitcell_array_inst.lx()

            mask_rail_x = grid_pos[3] + col_x_start

            write_mask_pin = self.write_driver_array_inst.get_pin("mask_bar[{}]".format(col))

            y_offset = self.write_driver_array_inst.by() - self.line_end_space - m3m4.height - self.m3_width

            offset = vector(write_mask_pin.lx(), y_offset)
            self.add_rect("metal3", offset=offset, height=write_mask_pin.by()-offset.y)
            self.add_rect("metal3", offset=offset, width=mask_rail_x - offset.x)
            self.add_contact(m3m4.layer_stack, offset=vector(mask_rail_x, y_offset+self.m3_width-m3m4.height))

            self.add_layout_pin("mask_in_bar[{}]".format(col), "metal4", offset=vector(mask_rail_x, pin_bottom),
                                height=y_offset - pin_bottom)

            # add data pin

            flop_din = self.data_in_flops_inst.get_pin("din[{}]".format(col))

            data_rail_x = grid_pos[2] + col_x_start

            y_offset = flop_din.by() - self.m2_width

            self.add_contact(m2m3.layer_stack, offset=vector(flop_din.lx(), y_offset))
            self.add_rect("metal2", offset=vector(flop_din.lx(), y_offset), height=flop_din.by()-y_offset)
            # high to fulfill min m3 requirement
            fill_width = max(utils.ceil(drc["minarea_metal3_drc"]/m3m4.height), abs(data_rail_x-flop_din.lx()))

            self.add_rect("metal3", offset=vector(flop_din.lx()-fill_width, y_offset), width=fill_width,
                          height=m3m4.height)
            self.add_contact(m3m4.layer_stack, offset=vector(data_rail_x, y_offset))
            self.add_layout_pin("DATA[{}]".format(col), "metal4", offset=vector(data_rail_x, pin_bottom),
                                height=y_offset - pin_bottom)

            # find clearance to route metal3 through
            clearances = utils.get_clearances(self.write_driver_array.driver, "metal3")

            max_clearance = max(clearances, key=lambda x: x[1] - x[0])
            bend_y = (0.5 * (max_clearance[0] + max_clearance[1]) + self.write_driver_array_inst.by()
                      - 0.5 * self.m3_width)

            # nor pin
            x_offset = col_x_start + grid_pos[5]

            sense_pin = self.sense_amp_array_inst.get_pin("nor[{}]".format(col))

            self.add_rect("metal4", offset=vector(sense_pin.lx(), bend_y),
                          height=sense_pin.by()-bend_y)
            self.add_rect("metal4", offset=vector(sense_pin.lx(), bend_y),
                          width=x_offset - sense_pin.lx() + self.m4_width)
            self.add_layout_pin("nor[{}]".format(col), "metal4", offset=vector(x_offset, pin_bottom),
                                height=bend_y + self.m4_width - pin_bottom)

            # and pin
            x_offset = col_x_start + grid_pos[0]
            sense_pin = self.sense_amp_array_inst.get_pin("and[{}]".format(col))

            self.add_rect("via3", offset=vector(x_offset, bend_y))
            self.add_rect("via3", offset=vector(sense_pin.lx(), bend_y))

            via_extension = utils.ceil(0.5*(m3m4.height - self.m3_width))

            self.add_rect("metal4", offset=vector(sense_pin.lx(), bend_y - via_extension),
                          height=sense_pin.by() - bend_y + via_extension)
            self.add_rect("metal3", offset=vector(x_offset-via_extension, bend_y),
                          width=sense_pin.lx() - x_offset + self.m4_width + 2*via_extension)
            self.add_layout_pin("and[{}]".format(col), "metal4", offset=vector(x_offset, pin_bottom),
                                height=bend_y + self.m4_width - pin_bottom + via_extension)
