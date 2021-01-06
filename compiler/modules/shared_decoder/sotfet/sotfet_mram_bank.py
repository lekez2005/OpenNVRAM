from base.contact import m2m3, m1m2, cross_m2m3, m3m4, contact
from base.design import POLY, METAL1, METAL3, METAL2
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.shared_decoder.cmos_bank import CmosBank
from modules.shared_decoder.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers
from tech import drc


class SotfetMramBank(CmosBank):
    rwl_driver = wwl_driver = None
    wordline_driver_inst = rwl_driver_inst = wwl_driver_inst = None
    wordline_en_rail = rwl_en_rail = None

    def add_pins(self):
        super().add_pins()
        self.add_pin("vref")

    @staticmethod
    def get_module_list():
        modules = CmosBank.get_module_list()
        modules = [x for x in modules if x not in ["wordline_driver"]]
        modules.extend(["rwl_driver", "wwl_driver", "br_precharge_array"])
        return modules

    def create_modules(self):
        super().create_modules()
        self.rwl_driver = self.create_module("rwl_driver", name="rwl_driver",
                                             rows=self.num_rows,
                                             buffer_stages=OPTS.wordline_buffers)
        self.wwl_driver = self.create_module("wwl_driver", name="wwl_driver",
                                             rows=self.num_rows,
                                             buffer_stages=OPTS.wordline_buffers)
        self.wordline_driver = self.rwl_driver

        self.br_precharge_array = self.create_module('br_precharge_array',
                                                     columns=self.num_cols,
                                                     bank=self)

    def connect_inst(self, args, check=True):
        last_mod = self.insts[-1].mod
        if last_mod.name == "sense_amp_array":
            args = args[:-2] + ["br_reset", "vref", "vdd", "gnd"]
        elif last_mod.name == "bitcell_array":
            args = []
            for col in range(self.num_cols):
                args.append("bl[{0}]".format(col))
                args.append("br[{0}]".format(col))
            for row in range(self.num_rows):
                args.append("rwl[{0}]".format(row))
                args.append("wwl[{0}]".format(row))
            args.append("gnd")
        elif self.insts[-1].name == "wordline_driver":
            args = [x.replace("wl", "rwl") for x in args]
        super().connect_inst(args, check)

    def add_precharge_array(self):
        y_offset = self.get_precharge_y()
        self.br_precharge_array_inst = self.add_inst(name="br_precharge_array",
                                                     mod=self.br_precharge_array,
                                                     mirror="MX",
                                                     offset=vector(0, y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        temp.extend(["br_precharge_en_bar", "vdd"])
        self.connect_inst(temp)

        y_offset = self.br_precharge_array_inst.uy() + self.precharge_array.height
        self.precharge_array_inst = self.add_inst(name="precharge_array",
                                                  mod=self.precharge_array,
                                                  mirror="MX",
                                                  offset=vector(0, y_offset))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
        temp.extend(["precharge_en_bar", "vdd"])
        self.connect_inst(temp)

    def route_vdd_pin(self, pin, add_via=True, via_rotate=90):
        if pin == self.precharge_array_inst.get_pin("vdd"):
            via_rotate = 90
        super().route_vdd_pin(pin, add_via, via_rotate)

    def create_control_buffers(self):
        self.control_buffers = SotfetMramControlBuffers()
        self.add_mod(self.control_buffers)

    def connect_control_buffers(self):
        connections = ["bank_sel_buf", "read_buf", "clk", "sense_trig", "clk_buf", "clk_bar",
                       "rwl_en", "wwl_en", "precharge_en_bar", "br_precharge_en_bar",
                       "write_en", "write_en_bar",
                       "sense_en", "tri_en", "tri_en_bar", "br_reset",
                       "vdd", "gnd"]
        if OPTS.mirror_sense_amp:
            connections.append("sense_en_bar")
        else:
            connections.append("sample_en_bar")
        self.connect_inst(connections)

    def get_control_rails_destinations(self):
        destination_pins = {
            "sense_en": self.sense_amp_array_inst.get_pins("en"),
            "tri_en": self.tri_gate_array_inst.get_pins("en"),
            "tri_en_bar": self.tri_gate_array_inst.get_pins("en_bar"),
            "br_reset": self.sense_amp_array_inst.get_pins("br_reset"),
            "precharge_en_bar": self.precharge_array_inst.get_pins("en"),
            "br_precharge_en_bar": self.br_precharge_array_inst.get_pins("en"),
            "clk_buf": self.mask_in_flops_inst.get_pins("clk"),
            "clk_bar": self.data_in_flops_inst.get_pins("clk"),
            "write_en": self.write_driver_array_inst.get_pins("en"),
            "write_en_bar": self.write_driver_array_inst.get_pins("en_bar"),
            "rwl_en": [],
            "wwl_en": [],
        }
        if OPTS.mirror_sense_amp:
            destination_pins["sense_en_bar"] = self.sense_amp_array_inst.get_pins("en_bar")
        else:
            destination_pins["sample_en_bar"] = self.sense_amp_array_inst.get_pins("sampleb")
            destination_pins["precharge_en_bar"] += self.sense_amp_array_inst.get_pins("preb")

        return destination_pins

    def get_control_names(self):
        control_names = ["sense_en", "tri_en", "tri_en_bar", "br_reset",
                         "br_precharge_en_bar", "precharge_en_bar", "clk_buf",
                         "clk_bar", "write_en", "write_en_bar",
                         "rwl_en", "wwl_en"]
        if OPTS.mirror_sense_amp:
            control_names.append("sense_en_bar")
        else:
            control_names.append("sample_en_bar")
        return control_names

    def add_control_rails(self):
        super().add_control_rails()
        self.wordline_en_rail = self.rwl_en_rail

    def get_precharge_y(self):
        if self.col_mux_array_inst is None:
            y_space = self.get_line_end_space(POLY)
            return self.sense_amp_array_inst.uy() + self.precharge_array.height + y_space
        else:
            return self.col_mux_array_inst.uy() + self.precharge_array.height

    def add_wordline_driver(self):
        """ Wordline Driver """
        # place wwl to the right of rwl

        # calculate space to enable placing one M2 fill
        fill_space = (self.get_parallel_space(METAL2) + self.fill_width +
                      self.get_wide_space(METAL2))

        wwl_x_offset = self.mid_vdd_offset - (self.wwl_driver.width + fill_space)
        rwl_x_offset = wwl_x_offset - self.wide_m1_space - self.rwl_driver.width

        rwl_connections = []
        wwl_connections = []
        for i in range(self.num_rows):
            rwl_connections.append("dec_out[{}]".format(i))
            wwl_connections.append("dec_out[{}]".format(i))
        for i in range(self.num_rows):
            rwl_connections.append("rwl[{}]".format(i))
            wwl_connections.append("wwl[{}]".format(i))
        rwl_connections.append("rwl_en")
        wwl_connections.append("wwl_en")
        rwl_connections.extend(["vdd", "gnd"])
        wwl_connections.extend(["vdd", "gnd"])

        names = ["rwl_driver", "wwl_driver"]
        x_offsets = [rwl_x_offset, wwl_x_offset]
        connections = [rwl_connections, wwl_connections]
        modules = [self.rwl_driver, self.wwl_driver]
        insts = []

        for i in range(2):
            inst = self.add_inst(name=names[i], mod=modules[i],
                                 offset=vector(x_offsets[i], self.bitcell_array_inst.by()))
            insts.append(inst)
            self.connect_inst(connections[i])
        self.wordline_driver_inst = insts[0]
        self.rwl_driver_inst, self.wwl_driver_inst = insts

    def route_bitcell(self):
        pass

    def route_precharge(self):
        self.route_vdd_pin(self.precharge_array_inst.get_pin("vdd"), via_rotate=0)
        self.route_vdd_pin(self.br_precharge_array_inst.get_pin("vdd"), via_rotate=90)
        for col in range(self.num_cols):
            # route bitlines
            for pin_name in ["bl", "br"]:
                full_name = pin_name + "[{}]".format(col)
                bitcell_pin = self.bitcell_array_inst.get_pin(full_name)
                if self.col_mux_array_inst is None:
                    sense_pin = self.sense_amp_array_inst.get_pin(full_name)
                    target_pins = [sense_pin, bitcell_pin]
                else:
                    col_mux_pin = self.col_mux_array_inst.get_pin(full_name)
                    self.add_rect(METAL2, offset=col_mux_pin.ul(), width=col_mux_pin.width(),
                                  height=bitcell_pin.by() - col_mux_pin.uy())
                    if not col % self.words_per_row == 0:
                        continue
                    bit = int(col / self.words_per_row)
                    sense_pin = self.sense_amp_array_inst.get_pin(pin_name +
                                                                  "[{}]".format(bit))
                    mux_pin = self.col_mux_array_inst.get_pin(pin_name +
                                                              "_out[{}]".format(bit))
                    target_pins = [sense_pin, mux_pin]

                bottom_pin, top_pin = target_pins

                via_offset = bottom_pin.ul() - vector(0, m2m3.height)

                self.add_contact(m2m3.layer_stack, offset=via_offset)
                self.add_contact(m3m4.layer_stack, offset=via_offset)
                fill_y = sense_pin.uy() - self.fill_height
                via_extension = drc["wide_metal_via_extension"]
                if pin_name == "bl":
                    x_offset = bitcell_pin.lx() - via_extension
                else:
                    x_offset = bitcell_pin.rx() - self.fill_width + via_extension
                self.add_rect(METAL3, offset=vector(x_offset, fill_y),
                              width=self.fill_width, height=self.fill_height)
                if top_pin.by() > bottom_pin.uy():
                    self.add_rect(METAL2, offset=bottom_pin.ul(), width=sense_pin.width(),
                                  height=top_pin.by() - bottom_pin.uy())

    def route_sense_amp(self):
        self.copy_layout_pin(self.sense_amp_array_inst, "vref", "vref")
        if OPTS.mirror_sense_amp:
            for pin in self.sense_amp_array_inst.get_pins("vdd"):
                self.route_vdd_pin(pin, via_rotate=0)
            for pin in self.sense_amp_array_inst.get_pins("gnd"):
                self.route_gnd_pin(pin)
        else:
            super().route_sense_amp()

    def route_wordline_driver(self):

        self.route_wwl_in()
        self.route_rwl_in()
        self.route_decoder_in()
        self.route_decoder_enable()

        pin_names = ["gnd", "vdd"]
        dest_rail = [self.mid_gnd, self.mid_vdd]
        for i in range(2):
            pin_name = pin_names[i]
            for pin in self.rwl_driver_inst.get_pins(pin_name):
                self.add_rect(pin.layer, offset=vector(self.rwl_driver_inst.lx(), pin.by()),
                              height=pin.height(),
                              width=dest_rail[i].cx() - self.rwl_driver_inst.lx())
                self.add_power_via(pin, dest_rail[i], via_rotate=0)

        # fill between rwl and wwl
        fill_rects = create_wells_and_implants_fills(
            self.rwl_driver.logic_buffer.buffer_mod.module_insts[-1].mod,
            self.wwl_driver.logic_buffer.logic_mod)

        for row in range(self.num_rows):
            for fill_rect in fill_rects:
                if row % 4 in [1, 3]:
                    continue
                if row % 4 == 0:
                    fill_rect = (fill_rect[0], self.wwl_driver.logic_buffer.height -
                                 fill_rect[2],
                                 self.wwl_driver.logic_buffer.height - fill_rect[1])
                y_shift = (self.wwl_driver_inst.by() +
                           int(row / 2) * self.rwl_driver.logic_buffer.height)
                self.add_rect(fill_rect[0], offset=vector(self.rwl_driver_inst.rx(),
                                                          y_shift + fill_rect[1]),
                              height=fill_rect[2] - fill_rect[1],
                              width=(self.wwl_driver_inst.lx() - self.rwl_driver_inst.rx() +
                                     self.wwl_driver.buffer_insts[0].lx()))

    def route_wwl_in(self):
        for row in range(self.num_rows):
            wwl_out = self.wwl_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_in = self.bitcell_array_inst.get_pin("wwl[{}]".format(row))
            bitcell_x = self.bitcell_array_inst.lx()

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

    def route_rwl_in(self):
        for row in range(self.num_rows):
            rwl_out = self.rwl_driver_inst.get_pin("wl[{}]".format(row))
            bitcell_in = self.bitcell_array_inst.get_pin("rwl[{}]".format(row))
            decoder_in = self.wwl_driver_inst.get_pin("in[{}]".format(row))
            bitcell_x = self.bitcell_array_inst.lx()

            x_end = self.wwl_driver_inst.rx() + self.get_parallel_space(METAL2) + 0.5 * self.fill_width

            if row % 2 == 0:
                # route below decoder in
                y_offset = decoder_in.by() - self.get_parallel_space(METAL3) - m2m3.height
                self.add_rect(METAL2, offset=vector(rwl_out.lx(), y_offset),
                              height=rwl_out.by() - y_offset)
                via_y = y_offset - cross_m2m3.first_layer_vertical_enclosure
                self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(rwl_out.lx(),
                                                                         via_y))
                self.connect_inst([])

                self.add_rect(METAL3, offset=vector(rwl_out.lx(), y_offset),
                              width=x_end - rwl_out.lx())

                y_bend = decoder_in.by() - self.get_parallel_space(METAL1) - self.m1_width
                x_offset = x_end - 0.5 * m2m3.height
                self.add_rect(METAL3, offset=vector(x_offset, y_offset),
                              height=y_bend - y_offset, width=x_end - x_offset)
                via_offset = vector(x_end + 0.5 * m2m3.height, y_bend)
                self.add_contact(m1m2.layer_stack, offset=via_offset, rotate=90)
                self.add_contact(m2m3.layer_stack, offset=via_offset, rotate=90)

                fill_y = y_bend + self.m3_width - self.fill_height
                self.add_rect(METAL2, offset=vector(x_end - 0.5 * self.fill_width, fill_y),
                              width=self.fill_width, height=self.fill_height)

                x_offset = bitcell_x - self.get_wide_space(METAL1) - self.m1_width
                self.add_rect(METAL1, offset=vector(x_end, y_bend), width=x_offset - x_end)
                offset = vector(x_offset, bitcell_in.by())
                self.add_rect(METAL1, offset=offset, height=y_bend + self.m1_width - offset.y)
                self.add_rect(METAL1, offset=offset, width=bitcell_x - offset.x)

            else:
                y_offset = decoder_in.uy() + self.get_parallel_space(METAL3) + (m2m3.height - self.m3_width)
                self.add_rect(METAL2, offset=rwl_out.ul(), height=y_offset - rwl_out.uy())
                via_y = y_offset - cross_m2m3.first_layer_vertical_enclosure
                self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(rwl_out.lx(), via_y))
                self.connect_inst([])

                self.add_rect(METAL3, offset=vector(rwl_out.lx(), y_offset),
                              width=x_end - rwl_out.lx())
                y_bend = y_offset + self.m3_width - self.fill_height - self.get_parallel_space(METAL2)
                offset = vector(x_end - 0.5 * self.m3_width, y_bend)
                self.add_rect(METAL3, offset=offset,
                              height=y_offset + self.m3_width - y_bend)
                self.add_contact(m1m2.layer_stack, offset=offset)
                self.add_contact(m2m3.layer_stack, offset=offset)
                self.add_rect(METAL2, offset=vector(x_end - 0.5 * self.fill_width,
                                                    y_bend + 0.5 * m1m2.height - 0.5 * self.fill_height),
                              width=self.fill_width, height=self.fill_height)

                x_offset = bitcell_x - self.get_wide_space(METAL1) - self.m1_width
                y_offset = y_bend + 0.5 * m1m2.height - 0.5 * self.m1_width
                self.add_rect(METAL1, offset=vector(x_end, y_offset), width=x_offset - x_end)

                self.add_rect(METAL1, offset=vector(x_offset, y_offset),
                              height=bitcell_in.uy() - y_offset)
                self.add_rect(METAL1, offset=vector(x_offset, bitcell_in.by()),
                              width=bitcell_x - x_offset)

    def route_decoder_in(self):
        for row in range(self.num_rows):
            wwl_in = self.wwl_driver_inst.get_pin("in[{}]".format(row))
            rwl_in = self.rwl_driver_inst.get_pin("in[{}]".format(row))
            self.add_rect(METAL3, offset=rwl_in.lr(), width=wwl_in.lx() - rwl_in.rx())
            self.copy_layout_pin(self.rwl_driver_inst, "in[{}]".format(row),
                                 "dec_out[{}]".format(row))

    def route_decoder_enable(self):
        control_rails = ["wwl_en_rail", "rwl_en_rail"]
        driver_instances = [self.wwl_driver_inst, self.rwl_driver_inst]
        for i in range(2):
            control_rail = getattr(self, control_rails[i])
            enable_in = driver_instances[i].get_pin("en")
            y_offset = enable_in.by() - self.m3_width - i * (self.m3_width + self.get_parallel_space(METAL3))
            self.add_contact(m2m3.layer_stack, offset=control_rail.ll())
            rail = self.add_rect(METAL2, offset=control_rail.ll(),
                                 height=y_offset - control_rail.by())

            self.add_contact(m2m3.layer_stack, offset=vector(control_rail.lx(),
                                                             y_offset + self.m2_width - m2m3.height))
            self.add_rect(METAL3, offset=vector(enable_in.lx(), y_offset),
                          width=control_rail.lx() - enable_in.lx())
            if i == 1:
                self.add_rect(METAL3, offset=vector(enable_in.lx(), y_offset),
                              height=enable_in.by() - y_offset)

            setattr(self, control_rails[i], rail)
