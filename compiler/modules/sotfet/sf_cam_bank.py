import math

from base import utils
from base.contact import contact, m1m2, m2m3
from base.vector import vector
from globals import OPTS
from modules import bank
from modules.sotfet.current_mirror import current_mirror
from modules.sotfet.logic_buffers import LogicBuffers
from modules.sotfet.sf_bitline_buffer_array import SfBitlineBufferArray
from modules.sotfet.sf_bitline_logic_array import SfBitlineLogicArray
from modules.sotfet.sot_wl_driver_array import sot_wl_driver_array
from tech import drc


class SfCamBank(bank.bank):
    separate_vdd = False
    bitcell = bitcell_array = wordline_driver = decoder = search_sense_amp_array = ml_precharge_array = None
    msf_data_in = msf_address = tag_flop_array = bitline_buffer_array = bitline_logic_array = logic_buffers = None

    bitcell_array_inst = ml_precharge_array_inst = search_sense_inst = tag_flop_array_inst = row_decoder_inst = None
    bitline_buffer_array_inst = bitline_logic_array_inst = data_in_flops_inst = mask_in_flops_inst = None
    wordline_driver_inst = logic_buffers_inst = None
    address_flops = []

    def create_modules(self):

        self.bitcell = self.create_module('bitcell')
        self.bitcell_array = self.create_module('bitcell_array', cols=self.num_cols, rows=self.num_rows)
        self.create_wordline_driver()
        # self.wordline_driver = self.create_module('wordline_driver', rows=self.num_rows)
        self.search_sense_amp_array = self.create_module('search_sense_amp_array', rows=self.num_rows)
        self.ml_precharge_array = self.create_module('ml_precharge_array', rows=self.num_rows,
                                                     size=OPTS.ml_precharge_size)
        self.msf_data_in = self.create_module('ms_flop_array', columns=self.word_size, word_size=self.word_size,
                                              align_bitcell=True)

        self.horizontal_flop = self.create_module('ms_flop_horz_pitch')

        self.tag_flop_array = self.create_module('tag_flop_array', rows=self.num_rows)
        self.decoder = self.create_module('decoder', rows=self.num_rows)

        self.bitline_buffer_array = SfBitlineBufferArray(word_size=self.num_cols)
        self.add_mod(self.bitline_buffer_array)
        self.create_bitline_logic()

    def create_wordline_driver(self):
        self.wordline_driver = sot_wl_driver_array(rows=self.num_rows)
        self.add_mod(self.wordline_driver)

        self.current_mirror = current_mirror()
        self.add_mod(self.current_mirror)

    def create_bitline_logic(self):
        self.bitline_logic_array = SfBitlineLogicArray(word_size=self.word_size)
        self.add_mod(self.bitline_logic_array)

        self.logic_buffers = LogicBuffers()
        self.add_mod(self.logic_buffers)

    def add_modules(self):
        self.add_bitcell_array()
        self.add_search_sense_amp_array()

        self.add_bitline_logic()
        #
        self.add_data_mask_flops()
        #
        self.calculate_rail_offsets()
        #
        self.add_ml_precharge_array()
        self.add_wordline_driver()
        self.add_row_decoder()
        #
        self.add_logic_buffers()
        self.add_msf_address()

    def route_layout(self):
        self.create_rails()

        self.width = self.right_vdd.rx() - self.left_gnd.lx()
        self.height = self.left_vdd.height()

        self.route_precharge_to_bitcell_array()

        self.route_msf_address()
        self.route_wordline_driver()
        self.route_right_logic_buffer()

        self.calculate_rail_vias()

        self.route_vdd_supply()
        self.route_gnd_supply()
        self.connect_supply_rails()
        self.add_layout_pins()

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        self.bitcell_array_inst = self.add_inst(name="bitcell_array", mod=self.bitcell_array, offset=vector(0, 0))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
            temp.append("ml[{0}]".format(j))
        temp.extend(["gnd"])
        self.connect_inst(temp)

    def add_ml_precharge_array(self):
        self.ml_precharge_array_inst = self.add_inst(name="ml_precharge_array", mod=self.ml_precharge_array,
                                                     offset=vector(self.ml_precharge_x_offset, 0))
        temp = [self.prefix + "matchline_chb"]
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        temp.extend(["vdd", "gnd"])
        if self.separate_vdd:
            temp.append("vdd_decoder")
        self.connect_inst(temp)

    def add_search_sense_amp_array(self):
        self.search_sense_inst = self.add_inst(name="search_sense_amps", mod=self.search_sense_amp_array,
                                               offset=self.bitcell_array_inst.lr())
        temp = []
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("search_out[{0}]".format(i))
        temp.append(self.prefix + "sense_amp_en")
        temp.append("search_ref")
        vdd_name = "vdd_sense_amp" if self.separate_vdd else "vdd"
        temp.append(vdd_name)
        temp.append("gnd")
        self.connect_inst(temp)

    def add_row_decoder(self):
        x_offset = self.wordline_driver_inst.lx() - self.decoder.row_decoder_width
        offset = vector(x_offset, -self.decoder.predecoder_height)
        self.row_decoder_inst = self.add_inst(name="row_decoder", mod=self.decoder, offset=offset)

        temp = []
        for i in range(self.row_addr_size):
            temp.append("A[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out[{0}]".format(j))
        vdd_name = "vdd_decoder" if self.separate_vdd else "vdd"
        temp.extend([vdd_name, "gnd"])
        self.connect_inst(temp)

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
        vdd = "vdd_wordline" if self.separate_vdd else "vdd"
        nwell_vdd = "vdd_decoder" if self.separate_vdd else "vdd"
        temp.extend(["vbias_p", "vbias_n", vdd, nwell_vdd, "gnd"])
        self.connect_inst(temp)

    def add_bitline_buffers(self):
        offset = vector(0, -self.bitline_buffer_array.height)
        self.bitline_buffer_array_inst = self.add_inst(name="bitline_buffer", mod=self.bitline_buffer_array,
                                                       offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("bl_val[{0}]".format(i))
            connections.append("br_val[{0}]".format(i))
        for i in range(0, self.bitline_buffer_array.columns, self.words_per_row):
            connections.append("bl[{0}]".format(i))
            connections.append("br[{0}]".format(i))
        vdd_name = "vdd_bitline_buffer" if self.separate_vdd else "vdd"
        connections.extend([vdd_name, "gnd"])
        self.connect_inst(connections)

    def add_bitline_logic(self):

        self.add_bitline_buffers()

        offset = self.bitline_buffer_array_inst.ll() - vector(0, self.bitline_logic_array.height)
        self.bitline_logic_array_inst = self.add_inst(name="bitline_logic", mod=self.bitline_logic_array, offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("data_in[{0}]".format(i))
            connections.append("data_in_bar[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("mask_in[{0}]".format(i))
            connections.append("mask_in_bar[{0}]".format(i))
        for i in range(0, self.bitline_logic_array.columns, self.bitline_logic_array.words_per_row):
            connections.append("bl_val[{0}]".format(i))
            connections.append("br_val[{0}]".format(i))
        vdd_name = "vdd_bitline_logic" if self.separate_vdd else "vdd"
        connections.extend([self.prefix + "write_bar", self.prefix + "search_cbar", vdd_name, "gnd"])

        self.connect_inst(connections)

    def add_data_mask_flops(self):
        data_connections = []
        mask_connections = []
        vdd_name = "vdd_data_flops" if self.separate_vdd else "vdd"
        for i in range(self.word_size):
            data_connections.append("DATA[{}]".format(i))
            mask_connections.append("MASK[{}]".format(i))
        for i in range(self.word_size):
            data_connections.extend("data_in[{0}] data_in_bar[{0}]".format(i).split())
            mask_connections.extend("mask_in[{0}] mask_in_bar[{0}]".format(i).split())
        clk_power = [self.prefix + "clk_buf", vdd_name, "gnd"]
        data_connections.extend(clk_power)
        mask_connections.extend(clk_power)

        offset = self.get_data_flops_offset()
        self.data_in_flops_inst = self.add_inst("data_in", mod=self.msf_data_in, offset=offset)
        self.connect_inst(data_connections)

        offset = self.get_mask_flops_offset()

        self.mask_in_flops_inst = self.add_inst("mask_in", mod=self.msf_data_in, offset=offset)
        self.connect_inst(mask_connections)

    def get_data_flops_offset(self):
        return self.bitline_logic_array_inst.ll() - vector(0, self.msf_data_in.height)

    def get_mask_flops_offset(self):
        # align top gnd pin with bottom gnd pin
        gnd_pins = self.msf_data_in.get_pins("gnd")
        top_pin = max(gnd_pins, key=lambda x: x.uy())
        bottom_pin = min(gnd_pins, key=lambda x: x.by())

        y_offset = self.data_in_flops_inst.by() + bottom_pin.uy() - top_pin.uy()

        return vector(self.data_in_flops_inst.lx(), y_offset)

    def add_logic_buffers(self):

        self.logic_buffers_inst = self.add_inst("logic_buffers", mod=self.logic_buffers,
                                                offset=vector(self.logic_buffers_x + self.logic_buffers.width,
                                                              self.logic_buffers_bottom), mirror="MY")
        connections = ["bank_sel", "clk", "search"]
        connections.extend([self.prefix + x for x in ["clk_buf", "write_bar", "search_cbar", "sense_amp_en",
                                                      "wordline_en", "matchline_chb"]])
        vdd_name = "vdd_logic_buffers" if self.separate_vdd else "vdd"
        connections.extend([vdd_name, "gnd"])
        self.connect_inst(connections)

        self.min_point = min(self.logic_buffers_inst.by() - self.m3_pitch,
                             self.row_decoder_inst.by()-0.5*self.rail_height)

    def add_msf_address(self):
        name_template = "addr_flop_{}"
        addr_in = "ADDR[{}]"
        addr_out = "A[{}]"
        addr_out_bar = "ABAR[{}]"
        # add flops below decoder
        if self.address_flops_vert == 2:
            x_offset = self.row_decoder_inst.rx() - self.horizontal_flop.width - 3 * self.m2_pitch
            y_offset = self.row_decoder_inst.by() - self.decoder_flop_space - self.horizontal_flop.height
            mirrors = ["R0", "MX"]
            vdd_name = "vdd_decoder" if self.separate_vdd else "vdd"
            for i in range(2):
                instance = self.add_inst(name_template.format(i), mod=self.horizontal_flop,
                                         offset=vector(x_offset, y_offset), mirror=mirrors[i])
                self.address_flops.append(instance)
                self.connect_inst([addr_in.format(i), addr_out.format(i), addr_out_bar.format(i), self.prefix+"clk_buf",
                                   vdd_name, "gnd"])

        # add flops below mask flops
        y_offset = self.logic_buffers_bottom + self.logic_buffers.height - self.horizontal_flop.height
        x_offset = self.address_flop_x
        for i in range(self.address_flops_vert, self.num_address_bits):
            instance = self.add_inst(name_template.format(i), mod=self.horizontal_flop,
                                     offset=vector(x_offset+self.horizontal_flop.width, y_offset), mirror="MY")
            self.address_flops.append(instance)
            vdd_name = "vdd_logic_buffers" if self.separate_vdd else "vdd"
            self.connect_inst([addr_in.format(i), addr_out.format(i), addr_out_bar.format(i), self.prefix + "clk_buf",
                               vdd_name, "gnd"])
            x_offset += self.horizontal_flop.width

    def calculate_rail_offsets(self):
        # calculate position of logic buffers
        # get decoder bottom
        self.num_address_bits = int(math.log(self.num_words, 2))
        self.m3_pitch = m2m3.width + self.parallel_line_space

         # first assume two flops fit below decoder

        num_horizontal_rails = self.get_num_horizontal_rails() - 2

        self.logic_buffers_bottom = (self.mask_in_flops_inst.by() - (1+num_horizontal_rails)*self.m3_pitch -
                                     self.logic_buffers.height)

        decoder_bottom = - self.decoder.predecoder_height

        flop_vdd = self.horizontal_flop.get_pin("vdd")
        self.decoder_flop_space = 0.5*self.rail_height + 0.5*flop_vdd.height() + self.wide_m1_space

        if decoder_bottom - self.decoder_flop_space - 2*self.horizontal_flop.height < self.logic_buffers_bottom:
            # can't fit two flops below decoder so all flops are to the side of the logic buffers
            self.address_flops_horz = self.num_address_bits
            self.address_flops_vert = 0
            num_horizontal_rails = self.get_num_horizontal_rails()
            self.logic_buffers_bottom = (self.mask_in_flops_inst.by() - (1+num_horizontal_rails)*self.m3_pitch -
                                         self.logic_buffers.height)
        else:
            self.address_flops_horz = self.num_address_bits - 2
            self.address_flops_vert = 2

        self.num_left_rails = self.get_num_left_rails()

        self.right_gnd_x_offset = self.get_right_gnd_offset()
        self.left_vdd_x_offset = self.right_gnd_x_offset - self.wide_m1_space - self.vdd_rail_width

        self.left_rail_x = (self.left_vdd_x_offset - (self.num_left_rails-1)*self.m2_pitch - self.m2_width -
                            self.wide_m1_space)  # to the left of the data flops

        # find left edge of decoder
        self.ml_precharge_x_offset = -max(abs(self.left_rail_x) - self.parallel_line_space, self.ml_precharge_array.width)
        row_decoder_x = self.ml_precharge_x_offset - self.wordline_driver.width - self.decoder.row_decoder_width
        if row_decoder_x > self.left_rail_x - self.decoder.width - self.parallel_line_space:
            row_decoder_x = self.left_rail_x - self.decoder.width - self.parallel_line_space
            self.ml_precharge_x_offset = (row_decoder_x + self.wordline_driver.width
                                          + self.decoder.row_decoder_width)

        self.address_flop_x = self.bitcell_array.body_tap.width + self.line_end_space
        self.logic_buffers_x = (self.address_flop_x + self.address_flops_horz*self.horizontal_flop.width +
                                2*self.poly_pitch)

        self.right_rail_x = max(self.mask_in_flops_inst.rx(),
                                self.logic_buffers_x + self.logic_buffers.width) + 2 * self.m2_pitch  # to the right of data flops

    def get_right_gnd_offset(self):
        body_tap_width = self.bitcell_array.body_tap.width
        return body_tap_width - self.wide_m1_space - self.vdd_rail_width

    def get_num_horizontal_rails(self):
        left_vertical_rails = ["ml_chb", "wordline_en"]
        return self.num_address_bits + len(left_vertical_rails)

    def get_num_left_rails(self):
        # vbias_p, vbias_n, ml_chb, wordline_en, 2 will be below decoder
        return self.num_address_bits - self.address_flops_vert + 4

    def create_rails(self):
        rail_y = self.address_flops[-1].get_pin("vdd").uy()
        # first two address rails
        if self.address_flops_vert == 2:
            bottoms = [self.address_flops[i].get_pin("dout").uy() for i in [0, 1]]
            for i in range(self.address_flops_vert):
                addr_pin = self.row_decoder_inst.get_pin("A[{}]".format(i))
                rect = self.add_rect("metal2", offset=vector(addr_pin.lx(), bottoms[i]),
                                     height=addr_pin.by()-bottoms[i])
                setattr(self, "addr_rail_{}".format(i), rect)

        # other address rails
        rail_x = self.left_rail_x
        previous_y = current_y = 100.0
        for i in range(self.address_flops_vert, self.num_address_bits):
            addr_pin = self.row_decoder_inst.get_pin("A[{}]".format(i))
            if not addr_pin.by() == previous_y:
                previous_y = addr_pin.by()
                current_y = previous_y
            else:
                current_y = current_y + self.line_end_space + m2m3.second_layer_height

            rect = self.add_rect("metal2", offset=vector(rail_x, rail_y),
                                 height=current_y - rail_y)
            setattr(self, "addr_rail_{}".format(i), rect)
            rail_y += self.m3_pitch
            rail_x += self.m2_pitch

        self.add_left_right_rails(rail_x, rail_y)

        # vdd and gnd rails
        top = self.bitcell_array_inst.uy()
        x_offsets = [self.search_sense_inst.rx() + self.wide_m1_space, self.left_vdd_x_offset,
                     self.row_decoder_inst.lx() - self.wide_m1_space - self.vdd_rail_width, self.right_gnd_x_offset]
        layers = ["metal1", "metal2", "metal1", "metal2"]
        pin_names = ["vdd", "vdd", "gnd", "gnd"]
        attribute_names = ["right_vdd", "left_vdd", "left_gnd", "right_gnd"]
        for i in range(4):
            pin = self.add_layout_pin(pin_names[i], layers[i], offset=vector(x_offsets[i], self.min_point),
                                      width=self.vdd_rail_width, height=top-self.min_point)
            setattr(self, attribute_names[i], pin)

    def add_left_right_rails(self, rail_x, rail_y):
        top_y = -self.line_end_space - m2m3.second_layer_height
        # vbias_n and vbias_p
        pin_names = ["vbias_n", "vbias_p"]
        for i in range(2):
            self.add_layout_pin(pin_names[i], "metal2", offset=vector(rail_x, self.min_point),
                                height=top_y - self.min_point)
            rail_x += self.m2_pitch
        # ml_chb, wordline_en
        for rail_name in ["wordline_en", "ml_chb"]:
            rect = self.add_rect("metal2", offset=vector(rail_x, rail_y), height=top_y - rail_y)
            setattr(self, rail_name + "_rail", rect)
            rail_y += self.m3_pitch
            rail_x += self.m2_pitch

        # right rails
        rail_y = self.address_flops[-1].get_pin("vdd").uy()
        rail_x = self.right_rail_x
        rail_names = ["clk_buf", "write_bar", "search_cbar", "sense_en"]
        top_clk = max(self.data_in_flops_inst.get_pins("clk"), key=lambda x: x.uy())
        top_search_cbar = max(self.bitline_logic_array_inst.get_pins("search_cbar"), key=lambda x: x.uy())
        top_write_bar = max(self.bitline_logic_array_inst.get_pins("write_bar"), key=lambda x: x.uy())
        rail_tops = [top_clk.uy(), top_write_bar.uy(), top_search_cbar.uy(), top_y]
        rail_y += 3 * self.m3_pitch
        for i in range(len(rail_names)):
            rail_name = rail_names[i]
            rect = self.add_rect("metal2", offset=vector(rail_x, rail_y), height=rail_tops[i] - rail_y)
            setattr(self, rail_name + "_rail", rect)
            rail_y -= self.m3_pitch
            rail_x += self.m2_pitch

    def route_precharge_to_bitcell_array(self):

        self.connect_matchlines()
        # connect vdd pin
        ml_pin = self.bitcell_array_inst.get_pin("ml[0]")
        contact_size = [2, 1]
        # make dummy contact for measurements
        dummy_contact = contact(m1m2.layer_stack, dimensions=contact_size)
        x_offset = (min(ml_pin.lx() - self.line_end_space, getattr(self, 'left_vdd').lx()) -
                    dummy_contact.second_layer_height)

        vdd_pins = self.ml_precharge_array_inst.get_pins("vdd")
        for vdd_pin in vdd_pins:
            self.add_contact_center(m1m2.layer_stack,
                                    offset=vector(self.left_vdd.lx()+0.5*dummy_contact.second_layer_height,
                                                                    vdd_pin.cy()), size=contact_size, rotate=90)
            self.add_rect("metal1", offset=vdd_pin.lr(), width=self.left_vdd_x_offset-vdd_pin.rx(),
                          height=dummy_contact.first_layer_height)

        # join gnd pin
        gnd_pins = self.ml_precharge_array_inst.get_pins("gnd")
        x_offset = self.right_gnd.lx() + 0.5*self.vdd_rail_width

        for gnd_pin in gnd_pins:
            self.add_rect("metal1", offset=gnd_pin.lr(), width=x_offset-gnd_pin.rx(), height=gnd_pin.height())
            self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, gnd_pin.cy()), size=[2, 2])

        # connect ml_chb pin
        chb_pin = self.ml_precharge_array_inst.get_pin("precharge_bar")
        chb_rail = getattr(self, 'ml_chb_rail')
        self.add_rect("metal2", offset=chb_pin.ll()-vector(0, self.m2_width), width=chb_rail.rx()-chb_pin.lx())
        self.add_rect("metal2", offset=chb_rail.ul(), height=chb_pin.by()-chb_rail.uy())

        # buffer pin to rail
        buffer_pin = self.logic_buffers_inst.get_pin("ml_chb")
        self.add_rect("metal2", offset=buffer_pin.ul(), height=chb_rail.by() - buffer_pin.uy())
        self.add_rect("metal3", offset=chb_rail.ll(), width=buffer_pin.lx() - chb_rail.lx())
        self.add_contact(m2m3.layer_stack,
                         offset=vector(buffer_pin.lx() + 0.5 * self.m2_width + 0.5 * m2m3.first_layer_height,
                                       chb_rail.by()), rotate=90)
        self.add_contact(m2m3.layer_stack, offset=chb_rail.ll())

    def connect_matchlines(self):
        for row in range(self.num_rows):
            # join matchlines
            precharge_ml = self.ml_precharge_array_inst.get_pin("ml[{}]".format(row))
            bitcell_ml = self.bitcell_array_inst.get_pin("ml[{}]".format(row))
            self.add_rect("metal1", offset=vector(precharge_ml.lx(), bitcell_ml.by()),
                          width=bitcell_ml.lx()-precharge_ml.lx(), height=bitcell_ml.height())


    def route_msf_address(self):
        if self.address_flops_vert == 2:
            # join nwell and nimplant
            layer_names = ["nwell", "nimplant"]
            layer_purposes = ["drawing", "drawing"]
            flop_inst = self.address_flops[0]

            predecoders = self.decoder.pre2x4_inst + self.decoder.pre3x8_inst
            lowest_predecoder = min(predecoders, key=lambda x: x.by()).mod
            predecoder_inverter = lowest_predecoder.inv

            for i in range(2):
                rects = self.get_gds_layer_shapes(self.horizontal_flop, layer_names[i], layer_purposes[i])
                top_shape = max(rects, key=lambda x: x[1][1])
                leftmost = min(rects, key=lambda x: x[0][0])
                rightmost = max(rects, key=lambda x: x[1][0])
                y_offset = flop_inst.uy() + (top_shape[1][1] - flop_inst.height)

                inverter_rects = predecoder_inverter.get_layer_shapes(layer_names[i], layer_purposes[i])
                top_inverter_rect = max(inverter_rects, key=lambda x: x.by())
                rect_top = self.row_decoder_inst.by() + (predecoder_inverter.height - top_inverter_rect.uy())

                self.add_rect(layer_names[i], offset=vector(flop_inst.lx() + leftmost[0][0], y_offset),
                              width=rightmost[1][0]-leftmost[0][0], height=rect_top-y_offset)
        # join address flops nwell to logic buffer nwell

        buffer_offset, buffer_inverter = self.get_closest_logic_buffer_inverter()

        nwell = buffer_inverter.get_layer_shapes("nwell")[0]

        flop_nwell = max(self.get_gds_layer_shapes(self.horizontal_flop, "nwell"), key=lambda x: x[1][0])
        x_offset = self.address_flops[-1].rx() - flop_nwell[1][0] + self.horizontal_flop.width
        y_offset = buffer_offset + self.logic_buffers_inst.by() + nwell.by()

        self.add_rect("nwell", offset=vector(x_offset, y_offset),
                      height=nwell.uy()-nwell.by(), width=self.logic_buffers_inst.lx()-x_offset)

        # route clock
        y_offset = self.logic_buffers_inst.by() - self.m3_pitch
        if self.address_flops_vert == 2:
            x_offset = self.address_flops[0].get_pin("clk").lx() - self.line_end_space - self.m2_width
        else:
            x_offset = self.address_flops[0].get_pin("clk").rx()
        clk_buf_pin = self.logic_buffers_inst.get_pin("clk_buf")
        self.add_rect("metal3", offset=vector(x_offset, y_offset), width=clk_buf_pin.rx()-x_offset)
        self.add_rect("metal2", offset=vector(clk_buf_pin.lx(), y_offset), height=clk_buf_pin.by()-y_offset)
        self.add_contact_center(m2m3.layer_stack, offset=vector(clk_buf_pin.cx(), y_offset+0.5*self.m3_width),
                                rotate=90)

        # connect flops below mask flops to clk
        for i in range(self.address_flops_vert, self.num_address_bits):

            m2_fill_height = drc["minside_metal1_contact"]
            m2_fill_width = utils.ceil(self.minarea_metal1_contact/m2_fill_height)
            x_offset = self.address_flops[i].rx() - 0.5*m2_fill_width

            clk_pin = self.address_flops[i].get_pin("clk")
            self.add_rect_center("metal2", offset=vector(x_offset, clk_pin.cy()),
                                 width=m2_fill_width, height=m2_fill_height)
            self.add_rect("metal3", offset=vector(x_offset-0.5*self.m3_width, y_offset), height=clk_pin.cy()-y_offset)
            self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, clk_pin.cy()))
            self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset, clk_pin.cy()))
            self.add_rect("metal1", offset=clk_pin.lr(), width=x_offset-clk_pin.rx(), height=clk_pin.height())
        # connect flops below decoder to clk
        if self.address_flops_vert == 2:
            x_offset = self.address_flops[0].get_pin("clk").lx() - self.line_end_space - self.m2_width
            self.add_rect("metal2", offset=vector(x_offset, y_offset),
                          height=self.address_flops[0].get_pin("clk").uy()-y_offset)

            for i in range(self.address_flops_vert):
                clk_pin = self.address_flops[i].get_pin("clk")
                self.add_rect("metal1", offset=vector(x_offset, clk_pin.by()), width=clk_pin.lx()-x_offset,
                              height=clk_pin.height())
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset+0.5*self.m2_width, clk_pin.cy()))
                self.add_contact(m2m3.layer_stack, offset=vector(x_offset, y_offset))

        # connect address pins to decoder
        rail_y = self.address_flops[-1].get_pin("vdd").uy()

        for i in range(self.address_flops_vert, self.num_address_bits):
            address_rail = getattr(self, "addr_rail_{}".format(i))
            flop_dout = self.address_flops[i].get_pin("dout")
            self.add_rect("metal2", offset=flop_dout.ul(), height=rail_y-flop_dout.uy())
            self.add_rect("metal3", offset=vector(address_rail.lx(), rail_y), width=flop_dout.lx()-address_rail.lx())
            self.add_contact(m2m3.layer_stack,
                             offset=vector(flop_dout.lx() + 0.5*self.m2_width + 0.5*m2m3.first_layer_height,
                                           rail_y), rotate=90)
            addr_pin = self.row_decoder_inst.get_pin("A[{}]".format(i))

            self.add_contact(m2m3.layer_stack, offset=vector(address_rail.lx(), rail_y))

            if i == 0:  # connect directly
                if rail_y > addr_pin.uy():
                    y_offset = addr_pin.uy()
                else:
                    y_offset = rail_y
                self.add_rect("metal2", offset=vector(addr_pin.lx(), y_offset-self.m2_width),
                              width=address_rail.rx()-addr_pin.lx())
            elif rail_y < addr_pin.by() and utils.round_to_grid(address_rail.uy()) == utils.round_to_grid(addr_pin.by()):
                self.add_rect("metal2", offset=vector(addr_pin.lx(), address_rail.uy()),
                              width=address_rail.rx() - addr_pin.lx())
            else:
                if rail_y > addr_pin.by():
                    y_offset = address_rail.by()
                else:
                    y_offset = address_rail.uy() - m2m3.second_layer_height
                self.add_contact(m2m3.layer_stack, offset=vector(address_rail.lx(), y_offset))
                self.add_rect("metal3", offset=vector(addr_pin.rx(), y_offset+0.5*(m2m3.second_layer_height-self.m3_width)),
                              width=address_rail.lx()-addr_pin.rx())
                self.add_contact(m2m3.layer_stack, offset=vector(addr_pin.lx(), y_offset))

            rail_y += self.m3_pitch

        for i in range(self.address_flops_vert):
            flop_dout = self.address_flops[i].get_pin("dout")
            address_rail = getattr(self, "addr_rail_{}".format(i))
            self.add_rect("metal3", offset=vector(flop_dout.rx(), flop_dout.uy()-self.m3_width),
                          width=address_rail.rx()-flop_dout.rx())
            self.add_contact(m2m3.layer_stack, offset=vector(address_rail.lx(), flop_dout.uy()))

        # copy din pins
        for i in range(self.num_address_bits):
            self.copy_layout_pin(self.address_flops[i], "din", "ADDR[{}]".format(i))

    def get_closest_logic_buffer_inverter(self):
        buffer_offset = self.logic_buffers.wordline_buf_inst.by()
        buffer_inverter = self.logic_buffers.wordline_buf.buffer_mod.module_insts[-1].mod
        return buffer_offset, buffer_inverter

    def route_wordline_driver(self):
        pin_names = ["vbias_p", "vbias_n"]
        y_base = self.m2_width
        for i in [0, 1]:
            pin_name = pin_names[i]
            wl_pin = self.wordline_driver_inst.get_pin(pin_name)
            bank_pin = self.get_pin(pin_name)
            y_offset = bank_pin.uy() - y_base
            self.add_contact(m2m3.layer_stack, offset=vector(bank_pin.lx(),
                                                             y_offset-0.5*(m2m3.second_layer_height-self.m2_width)))
            self.add_rect("metal3", offset=vector(wl_pin.lx(), y_offset), width=bank_pin.lx()-wl_pin.lx())
            self.add_rect("metal3", offset=vector(wl_pin.lx(), y_offset), height=wl_pin.by()-y_offset)
            # self.add_contact(m2m3.layer_stack, offset=wl_pin.ll()-vector(0, 0.5*self.m2_width))
            y_base += (m2m3.second_layer_height + self.line_end_space)
            if i == 0:
                x_offset = wl_pin.lx() + m2m3.second_layer_height
            else:
                x_offset = wl_pin.rx()
            via_y = wl_pin.by() - 0.25*self.m2_width
            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, via_y), rotate=90)

        # connect wordline en to rail
        en_rail = getattr(self, "wordline_en_rail")
        en_pin = self.wordline_driver_inst.get_pin("en")
        y_offset = bank_pin.uy() - y_base
        self.add_contact(m2m3.layer_stack, offset=vector(en_rail.lx(), y_offset))
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), width=en_rail.lx() - en_pin.lx())
        self.add_rect("metal3", offset=vector(en_pin.lx(), y_offset), height=en_pin.by() - y_offset)
        self.add_contact(m2m3.layer_stack, offset=en_pin.ll())
        # connect buffer wordline output to rail
        buffer_pin = self.logic_buffers_inst.get_pin("wordline_en")
        self.add_rect("metal2", offset=buffer_pin.ul(), height=en_rail.by()-buffer_pin.uy())
        self.add_rect("metal3", offset=en_rail.ll(), width=buffer_pin.lx() - en_rail.lx())
        self.add_contact(m2m3.layer_stack,
                         offset=vector(buffer_pin.lx() + 0.5 * self.m2_width + 0.5 * m2m3.first_layer_height,
                                       en_rail.by()), rotate=90)
        self.add_contact(m2m3.layer_stack, offset=en_rail.ll())

        # connect wl pins to bitcells
        for row in range(self.num_rows):
            driver_pin = self.wordline_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_pin = self.bitcell_array_inst.get_pin("wl[{}]".format(row))

            x_offset = self.left_vdd.lx() - self.wide_m1_space - self.m2_width
            self.add_rect("metal3", offset=driver_pin.lr(), width=x_offset-driver_pin.rx())

            m2_fill_width = self.line_end_space
            m2_fill_height = utils.ceil(self.minarea_metal1_contact / m2_fill_width)

            if row % 2 == 0:
                via_y = driver_pin.by()
                fill_y = driver_pin.by()
            else:
                via_y = driver_pin.uy() - m2m3.second_layer_height
                fill_y = driver_pin.uy() - m2_fill_height

            fill_x = x_offset + self.m2_width - m2_fill_width

            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, via_y))
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_y))

            self.add_rect("metal2", offset=vector(fill_x, fill_y),
                                 width=m2_fill_width, height=m2_fill_height)

            self.add_rect("metal1", offset=vector(x_offset, driver_pin.by()),
                          width=bitcell_pin.lx()+self.m1_width-x_offset)
            self.add_rect("metal1", offset=bitcell_pin.lc(), height=driver_pin.cy()-bitcell_pin.cy())

    def route_right_logic_buffer(self):
        """Route logic buffer output pins to the right of the flops"""
        self.connect_logic_buffer_to_pin("clk_buf", "clk_buf", self.mask_in_flops_inst.get_pin("clk"))
        self.connect_logic_buffer_to_pin("clk_buf", "clk_buf", self.data_in_flops_inst.get_pin("clk"))

        self.connect_bitline_controls()

        # connect rail to sense_en pin
        self.connect_logic_buffer_to_pin("sense_amp_en", "sense_en")
        rail = getattr(self, "sense_en_rail")
        pin = self.search_sense_inst.get_pin("en")
        if pin.lx() < rail.lx():
            x_offset = pin.lx()
        else:
            x_offset = rail.rx()
        self.add_rect("metal2", offset=vector(x_offset, rail.uy()-self.m2_width), width=abs(pin.lx()-rail.lx()))

        self.add_rect("metal2", offset=vector(pin.lx(), rail.uy()), height=pin.by()-rail.uy(), width=pin.width())

        # create vcomp pin
        pin = self.search_sense_inst.get_pin("vcomp")
        x_offset = rail.rx() + self.wide_m1_space
        self.add_rect("metal2", offset=pin.ll(), width=x_offset-pin.lx())
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset, pin.by()+self.m2_width-m2m3.first_layer_height))
        self.add_layout_pin("search_ref", "metal3", offset=vector(x_offset, self.min_point), height=pin.by()-self.min_point)

    def connect_bitline_controls(self):
        for pin in self.bitline_logic_array_inst.get_pins("search_cbar"):
            self.connect_logic_buffer_to_pin("search_cbar", "search_cbar", pin)
        for pin in self.bitline_logic_array_inst.get_pins("write_bar"):
            self.connect_logic_buffer_to_pin("write_bar", "write_bar", pin)

    def connect_logic_buffer_to_pin(self, buffer_name, rail_name, target_pin=None):
        rail = getattr(self, rail_name+"_rail")
        buffer_pin = self.logic_buffers_inst.get_pin(buffer_name)
        self.add_rect("metal2", offset=buffer_pin.ul(), height=rail.by() - buffer_pin.uy())
        self.add_rect("metal3", offset=vector(buffer_pin.lx(), rail.by()), width=rail.lx()-buffer_pin.lx())
        self.add_contact(m2m3.layer_stack, offset=vector(buffer_pin.lx()+m2m3.second_layer_height, rail.by()),
                         rotate=90)
        self.add_contact(m2m3.layer_stack, offset=rail.ll())
        if target_pin is not None:
            self.add_rect("metal1", offset=target_pin.lr(), width=rail.lx()-target_pin.rx())
            self.add_contact_center(m1m2.layer_stack, offset=vector(rail.lx()+0.5*self.m2_width, target_pin.cy()))

    def get_collisions(self):
        return [
            (self.logic_buffers_inst.uy(), self.mask_in_flops_inst.by()),
            (self.logic_buffers_inst.by(), self.logic_buffers_inst.by()+self.m3_pitch)
        ]

    def route_vdd_supply(self):
        dummy_contact = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in self.get_right_vdd_modules():
            vdd_pins = instance.get_pins("vdd")
            for pin in vdd_pins:
                self.add_rect("metal1", offset=pin.lr(), width=self.right_vdd.rx()-pin.rx(),
                              height=pin.height())
                if not instance == self.search_sense_inst:
                    self.add_contact(m1m2.layer_stack,
                                     offset=vector(self.left_vdd.lx()+dummy_contact.second_layer_height, pin.by()),
                                     size=[2, 1], rotate=90)
                    self.add_rect("metal1", offset=vector(self.left_vdd.lx(), pin.by()),
                                  width=pin.lx()-self.left_vdd.lx(), height=pin.height())
        if not self.separate_vdd:
            for instance in [self.row_decoder_inst] + self.address_flops[:self.address_flops_vert]:
                vdd_pins = instance.get_pins("vdd")
                for pin in vdd_pins:
                    self.add_rect("metal1", offset=pin.lr(), width=self.left_vdd.lx()-pin.rx(), height=pin.height())

        # add metal1 rail along
        self.add_rect("metal1", offset=vector(self.left_vdd.lx(), self.min_point), width=dummy_contact.height,
                      height=-self.min_point)

    def get_right_vdd_modules(self):
        if not self.separate_vdd:
            return [self.logic_buffers_inst, self.mask_in_flops_inst, self.data_in_flops_inst,
                    self.bitline_buffer_array_inst, self.bitline_logic_array_inst, self.search_sense_inst]
        else:
            return []

    def route_bitline_logic_gnd(self):
        dummy_contact = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in [self.bitline_buffer_array_inst, self.mask_in_flops_inst, self.data_in_flops_inst,
                         self.address_flops[self.address_flops_vert]]:
            gnd_pins = instance.get_pins("gnd")
            for pin in gnd_pins:
                self.add_rect("metal1", offset=vector(self.right_gnd.lx(), pin.by()),
                              width=pin.lx() - self.right_gnd.lx(), height=pin.height())
                self.add_contact(m1m2.layer_stack,
                                 offset=vector(self.right_gnd.lx() + dummy_contact.second_layer_height, pin.by()),
                                 size=[2, 1], rotate=90)

        # bitline_logic_array_inst gnd needs special treatment
        # top gnd via goes down and bottom gnd goes up to avoid short with vdd
        gnd_pins = list(sorted(self.bitline_logic_array_inst.get_pins("gnd"), key=lambda x: x.by()))

        for i in range(len(gnd_pins)):
            pin = gnd_pins[i]

            self.add_rect("metal1", offset=vector(self.right_gnd.lx(), pin.by()),
                          width=pin.lx() - self.right_gnd.lx(), height=pin.height())
            self.add_contact_center(m1m2.layer_stack,
                             offset=vector(self.right_gnd.lx()+0.5*self.right_gnd.width(), pin.cy()),
                             size=[1, 2], rotate=90)

    def route_gnd_supply(self):

        for instance in [self.row_decoder_inst] + self.address_flops[:self.address_flops_vert]:
            gnd_pins = instance.get_pins("gnd")
            for pin in gnd_pins:
                self.add_rect("metal1", offset=vector(self.left_gnd.rx(), pin.by()), width=pin.lx()-self.left_gnd.rx(),
                              height=pin.height())

        self.route_bitline_logic_gnd()

        # connect logic_buffers gnd to address flops gnd
        logic_gnd = self.logic_buffers_inst.get_pin("gnd")
        flops_gnd = self.address_flops[-1].get_pin("gnd")
        self.add_rect("metal1", offset=flops_gnd.lr(), width=logic_gnd.lx() + logic_gnd.height()-flops_gnd.rx(),
                      height=flops_gnd.height())
        self.add_rect("metal1", offset=vector(logic_gnd.lx(), flops_gnd.by()), width=logic_gnd.height(),
                      height=logic_gnd.by()-flops_gnd.by())

    def connect_supply_rails(self):

        self.vdd_grid_rects = []

        for i in range(len(self.power_grid_vias)):
            if i % 2 == 0:
                rails_x = [self.left_vdd.lx(), self.right_vdd.rx()-self.m1mtop.second_layer_width]
                rail_name = "vdd"
                mirrors = ["R0", "MY"]
                via_x = [self.left_vdd.lx()+0.5*self.vdd_rail_width, self.right_vdd.rx()]
                via_mods = [self.m2mtop, self.m1mtop]
                self.vdd_grid_rects.append(self.add_rect(self.bottom_power_layer,
                                                         offset=vector(self.left_vdd.lx(), self.power_grid_vias[i]),
                                  height=self.grid_rail_height,
                                  width=self.right_vdd.rx() - self.left_vdd.lx()))
            else:
                rails_x = [self.left_gnd.lx()]
                rail_name = "gnd"
                mirrors = ["R0"]
                via_x = rails_x
                via_mods = [self.m1mtop]
            # add vertical rail
            for j in range(len(rails_x)):
                self.add_layout_pin(rail_name, layer=self.top_power_layer, offset=vector(rails_x[j], self.min_point),
                                    width=self.grid_rail_width, height=self.height)
                self.add_inst(via_mods[j].name, via_mods[j],
                              offset=vector(via_x[j], self.power_grid_vias[i]),
                              mirror=mirrors[j])
                self.connect_inst([])

    def add_layout_pins(self):
        for col in range(self.num_cols):
            self.copy_layout_pin(self.data_in_flops_inst, "din[{}]".format(col), "DATA[{}]".format(col))
            self.copy_layout_pin(self.mask_in_flops_inst, "din[{}]".format(col), "MASK[{}]".format(col))

        for pin_name in ["bank_sel", "clk", "search"]:
            self.copy_layout_pin(self.logic_buffers_inst, pin_name, pin_name)

    @staticmethod
    def get_module_list():
        modules = ["bitcell", "bitcell_array", "wordline_driver", "decoder", "search_sense_amp_array",
                   "ml_precharge_array", "ms_flop_array", "tag_flop_array", "ms_flop_horz_pitch"]
        return modules

    def add_pins(self):
        if hasattr(OPTS, 'separate_vdd'):
            self.separate_vdd = OPTS.separate_vdd
        else:
            self.separate_vdd = False
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))

        if self.separate_vdd:
            vdd_pins = ["vdd", "vdd_wordline", "vdd_decoder", "vdd_logic_buffers", "vdd_data_flops",
                        "vdd_bitline_buffer", "vdd_bitline_logic", "vdd_sense_amp"]
        else:
            vdd_pins = ["vdd"]

        for pin in ["bank_sel", "clk", "search", "search_ref"] + vdd_pins + ["gnd"]:
            self.add_pin(pin)
        self.add_wordline_pins()

    def add_wordline_pins(self):
        self.add_pin_list(["vbias_n", "vbias_p"])

    def setup_layout_constraints(self):
        pass

    def add_lvs_correspondence_points(self):
        """ This adds some points for easier debugging if LVS goes wrong.
        These should probably be turned off by default though, since extraction
        will show these as ports in the extracted netlist.
        """
        # Add the wordline names
        for i in range(self.num_rows):
            wl_name = "wl[{}]".format(i)
            wl_pin = self.bitcell_array_inst.get_pin(wl_name)
            self.add_label(text=wl_name,
                           layer="metal1",
                           offset=wl_pin.ll())

        # Add the bitline names
        for i in range(self.num_cols):
            bl_name = "bl[{}]".format(i)
            br_name = "br[{}]".format(i)
            bl_pin = self.bitcell_array_inst.get_pin(bl_name)
            br_pin = self.bitcell_array_inst.get_pin(br_name)
            self.add_label(text=bl_name,
                           layer="metal2",
                           offset=bl_pin.ll())
            self.add_label(text=br_name,
                           layer="metal2",
                           offset=br_pin.ll())

        for i in range(self.num_address_bits):
            pin = self.address_flops[i].get_pin("dout")
            self.add_label("A[{0}]".format(i), layer=pin.layer, offset=pin.ll())

