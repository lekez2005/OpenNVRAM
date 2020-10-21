from base import utils
from base.contact import contact, m1m2, m2m3, m3m4
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import BaselineBank
from modules.sotfet.current_mirror import current_mirror
from modules.sotfet.sf_bitline_buffer_array import SfBitlineBufferArray
from modules.sotfet.sf_bitline_logic_array import SfBitlineLogicArray
from modules.sotfet.sf_control_buffers import SfControlBuffers
from modules.sotfet.sot_wl_driver_array import sot_wl_driver_array
from tech import drc


class SfCamBank(BaselineBank):
    separate_vdd = False
    bitcell = bitcell_array = wordline_driver = decoder = search_sense_amp_array = ml_precharge_array = None
    msf_data_in = msf_address = tag_flop_array = bitline_buffer_array = bitline_logic_array = logic_buffers = None

    bitcell_array_inst = ml_precharge_array_inst = search_sense_inst = tag_flop_array_inst = row_decoder_inst = None
    bitline_buffer_array_inst = bitline_logic_array_inst = data_in_flops_inst = mask_in_flops_inst = None
    wordline_driver_inst = logic_buffers_inst = None
    address_flops = []

    def create_modules(self):
        super().create_modules()

        self.create_wordline_driver()
        self.search_sense_amp_array = self.create_module('search_sense_amp_array', rows=self.num_rows)
        self.ml_precharge_array = self.create_module('ml_precharge_array', rows=self.num_rows,
                                                     size=OPTS.ml_precharge_size)

        self.create_bitline_logic()

    def get_module_list(self):
        return ["bitcell", "decoder", "ms_flop_array", "wordline_driver", "ms_flop_horz_pitch",
                "bitcell_array", "ml_precharge_array", "search_sense_amp_array"]

    def get_control_names(self):
        return ["precharge_en_bar", "wordline_en", "clk_buf", "sense_amp_en"]

    def get_body_taps_bottom(self):
        return self.mask_in_flops_inst.by()

    def create_wordline_driver(self):
        self.wordline_driver = sot_wl_driver_array(rows=self.num_rows)
        self.add_mod(self.wordline_driver)

        self.current_mirror = current_mirror()
        self.add_mod(self.current_mirror)

    def create_control_buffers(self):
        self.control_buffers = SfControlBuffers()
        self.add_mod(self.control_buffers)

    def create_bitline_logic(self):

        self.bitline_buffer_array = SfBitlineBufferArray(word_size=self.num_cols)
        self.add_mod(self.bitline_buffer_array)

        self.bitline_logic_array = SfBitlineLogicArray(word_size=self.num_cols)
        self.add_mod(self.bitline_logic_array)

    def add_modules(self):
        self.add_control_buffers()
        self.add_read_flop()
        self.add_data_mask_flops()

        self.add_bitline_logic()

        self.add_bitcell_array()

        self.add_search_sense_amp_array()

        self.add_control_rails()

        self.add_ml_precharge_array()

        self.add_wordline_driver()
        self.add_row_decoder()

        self.add_vdd_gnd_rails()

    def route_layout(self):
        self.route_control_buffer()
        self.route_read_buf()
        self.route_precharge_to_bitcell_array()
        self.route_wordline_driver()
        self.route_wordline_in()
        self.route_right_logic_buffer()

        self.route_decoder()

        self.route_flops()

        self.route_vdd_supply()
        self.route_gnd_supply()

        self.add_layout_pins()
        #
        self.calculate_rail_vias()  # horizontal rail vias
        #
        self.add_decoder_power_vias()
        self.add_right_rails_vias()
        self.route_body_tap_supplies()

    def copy_sense_trig_pin(self):
        pass

    def connect_control_buffers(self):
        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"
        connections = ["bank_sel", "clk", "search_buf"]
        connections.extend([self.prefix + x for x in ["clk_buf", "bitline_en", "sense_amp_en",
                                                      "wordline_en", "precharge_en_bar"]])
        connections.extend([vdd_name, "gnd"])
        self.connect_inst(connections)

    def get_decoder_clk(self):
        return self.prefix + "clk_buf"

    def get_mask_clk(self):
        return self.prefix + "clk_buf"

    def get_data_clk(self):
        return self.prefix + "clk_buf"

    def get_mask_flops_y_offset(self):
        return self.trigate_y

    def get_data_flops_y_offset(self):
        # align top gnd pin with bottom gnd pin
        gnd_pins = self.msf_data_in.get_pins("gnd")
        top_pin = max(gnd_pins, key=lambda x: x.uy())
        bottom_pin = min(gnd_pins, key=lambda x: x.by())

        return self.mask_in_flops_inst.by() - bottom_pin.uy() + top_pin.uy()

    def get_control_rails_destinations(self):
        destination_pins = {
            "clk_buf": self.mask_in_flops_inst.get_pins("clk") + self.data_in_flops_inst.get_pins("clk"),
            "precharge_en_bar": [],
            "wordline_en": [],
        }
        return destination_pins

    def get_right_vdd_offset(self):
        return max(self.control_buffers_inst.rx(), self.search_sense_inst.rx(),
                   self.read_buf_inst.rx() + self.m2_pitch) + self.wide_m1_space

    def get_collisions(self):
        bitline_en_pins = self.bitline_logic_array_inst.get_pins("en")

        return [
            (self.control_buffers_inst.by(), self.mask_in_flops_inst.by()),

            (bitline_en_pins[0].uy(), bitline_en_pins[0].by()),
            (bitline_en_pins[1].uy(), bitline_en_pins[1].by()),

        ]

    def add_operation_flop(self, offset):
        vdd_name = "vdd_buffers" if OPTS.separate_vdd else "vdd"
        self.read_buf_inst = self.add_inst("search_buf", mod=self.control_flop, offset=offset, mirror="MY")
        self.connect_inst(["search", "clk", "search_buf", vdd_name, "gnd"])

        self.copy_layout_pin(self.read_buf_inst, "din", "search")

        # replace read pin with search pin
        original = self.control_buffers_inst.get_pin

        def get_pin(pin_name):
            if pin_name == "read":
                pin_name = "search"
            return original(pin_name)

        self.control_buffers_inst.get_pin = get_pin

    def add_bitline_logic(self):

        offset = self.data_in_flops_inst.ul()
        self.bitline_logic_array_inst = self.add_inst(name="bitline_logic", mod=self.bitline_logic_array, offset=offset)
        connections = []
        for i in range(self.word_size):
            connections.append("data_in[{0}]".format(i))
            connections.append("data_in_bar[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("mask_in[{0}]".format(i))
        for i in range(0, self.bitline_logic_array.columns, self.bitline_logic_array.words_per_row):
            connections.append("bl_val[{0}]".format(i))
            connections.append("br_val[{0}]".format(i))
        vdd_name = "vdd_bitline_logic" if self.separate_vdd else "vdd"
        connections.extend([self.prefix + "bitline_en", vdd_name, "gnd"])

        self.connect_inst(connections)

        self.add_bitline_buffers()

    def add_bitline_buffers(self):
        offset = self.bitline_logic_array_inst.ul()
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

    def add_bitcell_array(self):
        """ Adding Bitcell Array """
        offset = self.bitline_buffer_array_inst.ul()
        self.bitcell_array_inst = self.add_inst(name="bitcell_array", mod=self.bitcell_array, offset=offset)
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
            temp.append("ml[{0}]".format(j))
        temp.extend(["gnd"])
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

    def add_ml_precharge_array(self):
        # leave space for ml and wl vias
        pin_offset = self.ml_precharge_array.width - self.ml_precharge_array.get_pin("precharge_bar").rx()

        m2_fill_width = self.line_end_space

        space = self.wide_m1_space + m2_fill_width + self.parallel_line_space

        x_offset = self.mid_vdd_offset - space + pin_offset - self.ml_precharge_array.width
        self.ml_precharge_array_inst = self.add_inst(name="ml_precharge_array", mod=self.ml_precharge_array,
                                                     offset=vector(x_offset, self.bitcell_array_inst.by()))
        temp = [self.prefix + "precharge_en_bar"]
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        temp.extend(["vdd", "gnd"])
        if self.separate_vdd:
            temp.append("vdd_decoder")
        self.connect_inst(temp)

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
        vdd = "vdd_wordline" if self.separate_vdd else "vdd"
        nwell_vdd = "vdd_decoder" if self.separate_vdd else "vdd"
        temp.extend(["vbias_p", "vbias_n", vdd, nwell_vdd, "gnd"])
        self.connect_inst(temp)

    def route_precharge_to_bitcell_array(self):

        self.connect_matchlines()
        # connect vdd pin

        # connect ml_chb pin
        chb_pin = self.ml_precharge_array_inst.get_pin("precharge_bar")
        chb_rail = getattr(self, 'precharge_en_bar_rail')
        self.add_contact(m2m3.layer_stack, offset=chb_rail.ll())
        y_offset = chb_pin.by()
        self.add_rect("metal2", offset=vector(chb_pin.lx(), y_offset), width=chb_rail.lx() - chb_pin.lx())
        self.add_rect("metal2", offset=chb_rail.ul(), height=y_offset - chb_rail.uy())

    def connect_matchlines(self):
        for row in range(self.num_rows):
            # join matchlines
            precharge_ml = self.ml_precharge_array_inst.get_pin("ml[{}]".format(row))
            bitcell_ml = self.bitcell_array_inst.get_pin("ml[{}]".format(row))
            self.add_rect("metal1", offset=vector(precharge_ml.lx(), bitcell_ml.by()),
                          width=bitcell_ml.lx() - precharge_ml.lx(), height=bitcell_ml.height())

    def route_wordline_in(self):
        # route decoder in
        for row in range(self.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            wl_in = self.wordline_driver_inst.get_pin("in[{}]".format(row))
            self.add_rect("metal1", offset=vector(decoder_out.rx(), wl_in.by()),
                          width=wl_in.lx() - decoder_out.rx(), height=wl_in.height())

    def route_wordline_driver(self):
        self.copy_layout_pin(self.wordline_driver_inst, "vbias_p")
        self.copy_layout_pin(self.wordline_driver_inst, "vbias_n")

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

        # connect wl pins to bitcells
        for row in range(self.num_rows):
            driver_pin = self.wordline_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_pin = self.bitcell_array_inst.get_pin("wl[{}]".format(row))

            x_offset = self.mid_vdd.lx() - self.wide_m1_space - self.m2_width
            self.add_rect("metal3", offset=driver_pin.lr(), width=x_offset - driver_pin.rx())

            via_offset = vector(driver_pin.lx(), driver_pin.by() - 0.5 * m2m3.height)
            self.add_contact(m2m3.layer_stack, offset=via_offset)

            m2_fill_width = self.line_end_space
            m2_fill_height = utils.ceil(self.minarea_metal1_contact / m2_fill_width)

            fill_y = driver_pin.by() - 0.5 * m2_fill_height

            fill_x = x_offset + self.m2_width - m2_fill_width

            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, via_offset.y))
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_offset.y))

            self.add_rect("metal2", offset=vector(fill_x, fill_y),
                          width=m2_fill_width, height=m2_fill_height)

            self.add_rect("metal1", offset=vector(x_offset, via_offset.y),
                          height=bitcell_pin.cy() - via_offset.y())

            self.add_rect("metal1", offset=vector(x_offset, bitcell_pin.by()),
                          width=bitcell_pin.lx() - x_offset)

    def route_right_logic_buffer(self):
        """Route logic buffer output pins to the right of the flops"""

        x_offset = max(self.mask_in_flops_inst.rx(), self.read_buf_inst.rx()) + 2 * self.wide_m1_space
        # avoid clash with right_vdd
        x_offset = min(x_offset, self.right_vdd.lx() - self.wide_m1_space - 2 * self.m2_pitch)

        base_y = self.control_buffers_inst.get_pin("precharge_en_bar").uy() + 0.5 * self.rail_height + self.m2_space

        y_offset = base_y + 3 * self.control_rail_pitch
        self.sense_en_rail = self.add_rect("metal2", offset=vector(x_offset, y_offset),
                                           height=self.search_sense_inst.by() - self.rail_height
                                                  - m2m3.height - y_offset)
        x_offset += self.m2_pitch
        self.add_bitline_en_rail(base_y, x_offset)

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

    def add_bitline_en_rail(self, base_y, rail_x):
        y_offset = base_y + self.control_rail_pitch
        top_pin = max(self.bitline_logic_array_inst.get_pins("en"), key=lambda x: x.uy())
        self.bitline_en_rail = self.add_rect("metal2", offset=vector(rail_x, y_offset),
                                             height=top_pin.uy() - y_offset)

    def connect_bitline_controls(self):
        for pin in self.bitline_logic_array_inst.get_pins("en"):
            self.connect_logic_buffer_to_pin("bitline_en", "bitline_en", pin)

    def connect_logic_buffer_to_pin(self, buffer_name, rail_name, target_pin=None):
        rail = getattr(self, rail_name + "_rail")
        buffer_pin = self.control_buffers_inst.get_pin(buffer_name)
        self.add_rect("metal2", offset=buffer_pin.ul(), height=rail.by() - buffer_pin.uy())
        self.add_rect("metal3", offset=vector(buffer_pin.lx(), rail.by()), width=rail.lx() - buffer_pin.lx())
        self.add_contact(m2m3.layer_stack, offset=vector(buffer_pin.lx() + m2m3.second_layer_height, rail.by()),
                         rotate=90)
        self.add_contact(m2m3.layer_stack, offset=rail.ll())
        if target_pin is not None:
            if target_pin.layer == "metal1":
                via = m1m2
            else:
                via = m2m3
            self.add_rect(target_pin.layer, offset=target_pin.lr(), width=rail.lx() - target_pin.rx())
            self.add_contact_center(via.layer_stack, offset=vector(rail.lx() + 0.5 * self.m2_width, target_pin.cy()))

    def route_flops(self):
        # connect bitline logic out to bitline buffer in
        fill_width = self.m2_width
        fill_height = utils.ceil(drc["minarea_metal1_contact"] / fill_width)
        for col in range(self.num_cols):
            for pin_name in ["bl", "br"]:
                suffix = "[{}]".format(col)
                buffer_pin = self.bitline_buffer_array_inst.get_pin(pin_name + "_in" + suffix)
                logic_pin = self.bitline_logic_array_inst.get_pin(pin_name + suffix)

                self.add_rect("metal3", offset=logic_pin.ul(), height=buffer_pin.by() - logic_pin.uy() + self.m3_width)
                if logic_pin.lx() < buffer_pin.lx():
                    self.add_rect("metal3", offset=vector(logic_pin.lx(), buffer_pin.by()),
                                  width=buffer_pin.rx() - logic_pin.lx())
                else:
                    self.add_rect("metal3", offset=vector(buffer_pin.lx(), buffer_pin.by()),
                                  width=logic_pin.rx() - buffer_pin.lx())

                via_offset = vector(buffer_pin.lx(), buffer_pin.cy() - 0.5 * m1m2.height)
                self.add_contact(m1m2.layer_stack, offset=via_offset)
                self.add_contact(m2m3.layer_stack, offset=via_offset)

                fill_x = buffer_pin.cx() - 0.5 * fill_width
                fill_y = buffer_pin.uy() - fill_height

                self.add_rect("metal2", offset=vector(fill_x, fill_y), height=fill_height, width=fill_width)

        # connect data flops to bitline logic inputs
        for col in range(self.num_cols):
            for suffix in ["", "_bar"]:
                flop_pin = self.data_in_flops_inst.get_pin("dout" + suffix + "[{}]".format(col))
                logic_pin = self.bitline_logic_array_inst.get_pin("data" + suffix + "[{}]".format(col))
                self.add_rect("metal3", offset=flop_pin.ul(), height=logic_pin.by() - flop_pin.uy())
                self.add_contact(m3m4.layer_stack, offset=logic_pin.ll())

        # connect mask flops to bitline logic input
        for col in range(self.num_cols):
            flop_pin = self.mask_in_flops_inst.get_pin("dout" + "[{}]".format(col))
            logic_pin = self.bitline_logic_array_inst.get_pin("mask" + "[{}]".format(col))

            via_offset = vector(logic_pin.lx(), flop_pin.uy() - self.m3_width)
            self.add_rect("metal3", offset=via_offset, width=flop_pin.rx() - logic_pin.lx())
            self.add_contact(m3m4.layer_stack, offset=via_offset)
            self.add_rect("metal4", offset=via_offset, height=logic_pin.by() - flop_pin.uy() + self.m3_width)

    def route_vdd_supply(self):
        for instance in [self.bitline_buffer_array_inst, self.bitline_logic_array_inst]:
            for pin in instance.get_pins("vdd"):
                self.route_vdd_pin(pin, via_rotate=90)

        sample_via = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in [self.mask_in_flops_inst, self.data_in_flops_inst]:
            for pin in instance.get_pins("vdd"):
                self.add_rect("metal1", offset=vector(self.mid_vdd.lx(), pin.by()),
                              width=self.right_vdd.rx() - self.mid_vdd.lx(), height=pin.height())
                via_y = pin.uy() - sample_via.width + 0.5 * sample_via.width

                self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_vdd.cx(), via_y),
                                        size=[2, 1], rotate=90)
                self.add_contact_center(m1m2.layer_stack, offset=vector(self.right_vdd.cx(), via_y),
                                        size=[2, 1], rotate=90)

        for pin in self.search_sense_inst.get_pins("vdd"):
            self.add_rect("metal1", offset=pin.lr(),
                          width=self.right_vdd.rx() - pin.rx(), height=pin.height())
            self.add_power_via(pin, self.right_vdd, via_rotate=90)

        # decoder vdd
        for pin in self.row_decoder_inst.get_pins("vdd"):
            if pin.by() >= self.bitcell_array_inst.by() or pin.rx() <= self.row_decoder_inst.rx():
                self.add_rect("metal1", offset=vector(self.left_vdd.lx(), pin.by()),
                              width=pin.lx() - self.left_vdd.lx(), height=pin.height())
                self.add_power_via(pin, self.left_vdd, via_rotate=90)
            if pin.uy() >= self.bitcell_array_inst.by():
                self.add_rect("metal1", offset=pin.ll(), width=self.mid_vdd.rx() - pin.lx(), height=pin.height())
                self.add_power_via(pin, self.mid_vdd, via_rotate=90)

    def route_gnd_supply(self):
        self.route_bitline_gnds()

        for pin in self.search_sense_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=pin.lr(),
                          width=self.right_gnd.lx() - pin.rx(), height=pin.height())

        self.route_wordline_gnd()

        self.route_flop_gnd()

        # bitcell gnd
        for pin in self.bitcell_array_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), pin.by()),
                          width=pin.lx() - self.mid_gnd.lx(), height=pin.height())
            self.add_power_via(pin, self.mid_gnd, via_rotate=90)

        # decoder gnd
        for pin in self.row_decoder_inst.get_pins("gnd"):
            if pin.by() >= self.bitcell_array_inst.by() or pin.rx() <= self.row_decoder_inst.rx():
                self.add_rect("metal1", offset=vector(self.left_gnd.lx(), pin.by()),
                              width=pin.lx() - self.left_gnd.lx(), height=pin.height())

    def route_wordline_gnd(self):
        for pin in self.wordline_driver_inst.get_pins("gnd"):
            self.add_rect("metal1", offset=pin.lr(),
                          width=self.mid_gnd.lx() - pin.rx(), height=pin.height())
            self.add_power_via(pin, self.mid_gnd, via_rotate=90)

    def route_flop_gnd(self):
        # flops: vdd and gnd too close together
        sample_via = contact(m1m2.layer_stack, dimensions=[2, 1])
        for instance in [self.mask_in_flops_inst, self.data_in_flops_inst]:
            for pin in instance.get_pins("gnd"):
                self.add_rect("metal1", offset=vector(self.mid_gnd.lx(), pin.by()),
                              width=self.right_gnd.rx() - self.mid_gnd.lx(), height=pin.height())
                via_y = pin.by() + 0.5 * sample_via.width

                self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_gnd.cx(), via_y),
                                        size=[2, 1], rotate=90)

    def route_bitline_gnds(self):
        for instance in [self.bitline_buffer_array_inst, self.bitline_logic_array_inst]:
            for pin in instance.get_pins("gnd"):
                self.route_gnd_pin(pin, via_rotate=90)

    def add_pins(self):
        if hasattr(OPTS, 'separate_vdd'):
            self.separate_vdd = OPTS.separate_vdd
        else:
            self.separate_vdd = False
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("search_out[{0}]".format(i))
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

    def add_layout_pins(self):
        for col in range(self.num_cols):
            self.copy_layout_pin(self.data_in_flops_inst, "din[{}]".format(col), "DATA[{}]".format(col))
            self.copy_layout_pin(self.mask_in_flops_inst, "din[{}]".format(col), "MASK[{}]".format(col))
        for row in range(self.num_rows):
            self.copy_layout_pin(self.search_sense_inst, "dout[{}]".format(row), "search_out[{}]".format(row))

        for pin_name in ["bank_sel", "clk"]:
            self.copy_layout_pin(self.control_buffers_inst, pin_name, pin_name)

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
