from typing import Union

from base import utils
from base.contact import m3m4, m2m3, m1m2
from base.design import design
from base.geometry import rectangle
from base.pin_layout import pin_layout
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from tech import drc

design_control = Union[design, 'ControlBuffersMixin']


class ControlBuffersMixin:
    def connect_buffer_rails(self):
        if self.mirror_sense_amp:
            return

        self.buffer_dict = {}
        self.create_buffer_modules()

        self.via_enclose = drc["min_wide_metal_via_extension"]
        self.connect_clk()
        self.connect_sense_en()
        self.connect_tri_en()
        self.connect_write_en()
        self.connect_sample_b()
        self.connect_precharge_bar()

    def create_buffer_modules(self: design_control):
        module_defs = getattr(OPTS, "right_buffers", [])

        module_height = self.control_buffers.logic_heights

        modules_x_offset = OPTS.right_buffers_x
        y_offset = self.control_buffers_inst.uy() - module_height

        module_defs = list(sorted(module_defs, key=lambda x: self.control_buffers_inst.get_pin(x[0]).cx()))

        buffer_dict = self.buffer_dict

        min_rail_width = utils.ceil(self.get_fill_width()**2/self.m3_width)

        self.min_right_buffer_x = modules_x_offset

        for module_def in module_defs:
            buffer_sizes = module_def[2]
            module = BufferStage(buffer_stages=buffer_sizes, height=module_height, route_outputs=False)
            self.add_mod(module)

            input_rail_net = module_def[0]
            output_nets = module_def[1]

            if len(buffer_sizes) % 2 == 0:
                output_terms = output_nets if len(output_nets) == 2 else\
                    [input_rail_net+"_buffer_dummy", input_rail_net]
            else:
                output_terms = output_nets if len(output_nets) == 2 else \
                    [input_rail_net, input_rail_net + "_buffer_dummy"]

            module_inst = self.add_inst("right_buffer_{}".format(input_rail_net), mod=module,
                                        offset=vector(modules_x_offset, y_offset))

            self.connect_inst([input_rail_net] + output_terms + ["vdd", "gnd"])

            buffer_dict[output_nets[-1]] = module_inst.get_pin("out")
            if len(output_nets) == 2:
                buffer_dict[output_nets[0]] = module_inst.get_pin("out_inv")

            # connect input rail
            input_rail = getattr(self, input_rail_net+"_rail")
            original_buffer_pin = self.control_buffers_inst.get_pin(input_rail_net)
            in_pin = module_inst.get_pin("in")
            x_offset = in_pin.lx() - m1m2.height

            self.add_rect("metal3", offset=vector(original_buffer_pin.lx(), input_rail.by()),
                          width=x_offset-original_buffer_pin.lx())

            self.add_contact(m2m3.layer_stack, offset=vector(x_offset, input_rail.by()),
                             rotate=90)
            self.add_rect("metal2", offset=vector(x_offset-self.m2_width, in_pin.by()),
                          height=input_rail.by()+self.m2_width-in_pin.by())
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset+m1m2.height, in_pin.by()), rotate=90)

            # create output rails
            for net in output_nets:
                output_pin = buffer_dict[net]
                output_rail = getattr(self, net+"_rail")
                self.add_rect("metal2", offset=output_pin.ul(), height=output_rail.by()-output_pin.uy())
                self.add_rect("metal3", offset=vector(output_pin.lx(), output_rail.by()), width=min_rail_width)
                self.add_label(net, "metal3", vector(output_pin.lx(), output_rail.by()))
                self.add_contact(m2m3.layer_stack, offset=vector(output_pin.cx()+0.5*m2m3.height, output_rail.by()),
                                 rotate=90)

            modules_x_offset = module_inst.rx()

        self.max_right_buffer_x = modules_x_offset

    def get_all_control_pins(self: design_control, pin_name):
        pins = [self.control_buffers_inst.get_pin(pin_name)]
        if pin_name in self.buffer_dict:
            pins.append(self.buffer_dict[pin_name])
        return pins

    def find_closest_x(self: design, x_offset):
        """Find the closest first open space in the bitcell to the right"""
        x_shift = self.bitcell_array_inst.lx()
        invalid_offsets = [x + self.bitcell_array_inst.lx() + self.bitcell_array.body_tap.width
                           for x in self.bitcell_array.tap_offsets]

        bitcell_offsets = [x_shift + x for x in self.bitcell_array.bitcell_offsets]
        bitcell_offsets = filter(lambda x: x > x_offset and
                                           all([abs(x - y) > self.m2_width for y in invalid_offsets]),
                                 bitcell_offsets)
        return min(bitcell_offsets, key=lambda x: x - x_offset)

    @staticmethod
    def get_fill_width():
        return utils.ceil((drc["minarea_metal3_drc"])**0.5)

    def connect_rail_to_pin(self: design_control, source_rail: rectangle,
                            source_pin: pin_layout, destination_pin: pin_layout, x_shift=0.0):
        x_offset = self.find_closest_x(source_pin.rx()) + x_shift

        self.add_rect("metal3", offset=vector(source_pin.lx(), source_rail.by()),
                      width=x_offset-source_pin.lx(), height=self.m3_width)
        self.add_contact_center(m3m4.layer_stack, offset=vector(x_offset, source_rail.by()+0.5*self.m3_width),
                                rotate=90)
        self.add_rect("metal4", offset=vector(x_offset-0.5*self.m4_width, source_rail.by()),
                      height=destination_pin.cy()-source_rail.by())

        return x_offset

    def connect_clk(self: design_control):
        fill_width = self.get_fill_width()

        # clk_buf
        source_rail = self.clk_buf_rail
        dest_pin = self.mask_in_flops_inst.get_pin("clk")

        for source_pin in self.get_all_control_pins("clk_buf"):
                m4_x_offset = self.connect_rail_to_pin(source_rail, source_pin, dest_pin)
                for via in [m1m2, m2m3, m3m4]:
                    self.add_contact_center(via.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()), rotate=90)

                self.add_rect_center("metal3", offset=vector(m4_x_offset, dest_pin.cy()),
                                     width=fill_width, height=fill_width)
                self.add_rect("metal2", offset=vector(m4_x_offset - 0.5 * fill_width, dest_pin.uy() - fill_width),
                              width=fill_width, height=fill_width)

        source_rail = self.clk_bar_rail
        dest_pin = self.data_in_flops_inst.get_pin("clk")
        for source_pin in self.get_all_control_pins("clk_bar"):
            x_shift = 0.5 * fill_width + self.parallel_line_space
            m4_x_offset = self.connect_rail_to_pin(source_rail, source_pin, dest_pin,
                                                   x_shift=x_shift)
            cell_start_x = m4_x_offset - x_shift
            # use space between data and mask flops
            y_offset = 0.5*(self.mask_in_flops_inst.uy() + self.data_in_flops_inst.by())

            for via in [m2m3, m3m4]:
                self.add_contact_center(via.layer_stack, offset=vector(m4_x_offset, y_offset), rotate=90)

            offset = vector(cell_start_x-0.5*m1m2.height, y_offset-0.5*self.m2_width)
            self.add_rect("metal2", offset=offset, width=m4_x_offset-offset.x)
            self.add_rect("metal2", offset=offset, height=dest_pin.by()-offset.y)
            self.add_contact_center(m1m2.layer_stack, offset=vector(cell_start_x, dest_pin.cy()), rotate=90)

            self.add_rect_center("metal3", offset=vector(m4_x_offset, y_offset),
                                 width=fill_width, height=fill_width)

    def connect_sense_en(self: design_control):
        x_shift = self.bitcell_array.cell.get_pin("BL").rx() + self.line_end_space + 0.5*self.m4_width
        # sense_en
        dest_pin = self.sense_amp_array_inst.get_pin("en")
        for source_pin in self.get_all_control_pins("sense_en"):
            source_rail = self.sense_en_rail
            m4_x_offset = self.connect_rail_to_pin(source_rail, source_pin, dest_pin, x_shift=x_shift)

            if source_pin.cx() < dest_pin.cx(): # for left connection

                fill_height = m2m3.height
                fill_width = drc["minarea_metal3_drc"]/fill_height
                for via_layer in ["via1", "via2"]:
                    self.add_rect_center(via_layer, offset=vector(m4_x_offset, dest_pin.cy()))
                self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()))
                x_offset = m4_x_offset + 0.5 * self.m3_width + self.via_enclose - fill_width
                self.add_rect("metal2", offset=vector(x_offset, dest_pin.cy() - 0.5 * fill_height),
                              height=fill_height, width=fill_width)
                x_offset = m4_x_offset - self.m3_width - self.via_enclose
                self.add_rect("metal3", offset=vector(x_offset, dest_pin.cy() - 0.5 * fill_height),
                              height=fill_height, width=fill_width)
            else:
                sample_b_pin = self.sense_amp_array_inst.get_pin("sampleb")
                y_bend = 0.5*(sample_b_pin.cy() + dest_pin.cy()) - 0.5*self.m3_width
                self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, dest_pin.cy()),
                              height=y_bend-dest_pin.cy())
                tap_offsets = [x + self.bitcell_array_inst.lx() + 0.5 * self.bitcell_array.body_tap.width -
                               self.wide_m1_space
                               for x in self.bitcell_array.tap_offsets]
                closest_tap = min(tap_offsets, key=lambda x: abs(x - m4_x_offset))
                self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, y_bend+0.5*self.m3_width))
                self.add_rect("metal3", offset=vector(m4_x_offset, y_bend), width=closest_tap-m4_x_offset)
                self.add_contact_center(m2m3.layer_stack, offset=vector(closest_tap+0.5*self.m2_width,
                                                                        y_bend+0.5*self.m3_width))
                self.add_rect("metal2", offset=vector(closest_tap, dest_pin.cy()), height=y_bend-dest_pin.cy())
                self.add_contact_center(m1m2.layer_stack, offset=vector(closest_tap+0.5*self.m2_width,
                                                                        dest_pin.cy()), rotate=90)

    def connect_tri_en(self: design_control):
        fill_width = self.get_fill_width()
        x_shift = self.bitcell_array.cell.get_pin("BL").rx() + self.line_end_space + 0.5 * self.m4_width
        dest_pin = self.tri_gate_array_inst.get_pin("en")
        for source_pin in self.get_all_control_pins("tri_en"):
            source_rail = self.tri_en_rail
            m4_x_offset = self.connect_rail_to_pin(source_rail, source_pin, dest_pin, x_shift=x_shift)

            self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()), rotate=90)
            self.add_contact_center(m2m3.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()), rotate=90)
            self.add_rect_center("metal3", offset=vector(m4_x_offset, dest_pin.by()+0.5*fill_width),
                                 width=fill_width, height=fill_width)

        # tri_en_bar
        dest_pin = self.tri_gate_array_inst.get_pin("en_bar")
        for source_pin in self.get_all_control_pins("tri_en_bar"):
            m4_x_offset = self.connect_rail_to_pin(self.tri_en_bar_rail, source_pin, dest_pin)
            self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()), rotate=90)
            self.add_contact_center(m2m3.layer_stack, offset=vector(m4_x_offset, dest_pin.cy()), rotate=90)
            self.add_rect_center("metal3", offset=vector(m4_x_offset, dest_pin.cy()),
                                 width=fill_width, height=fill_width)

    def connect_write_en(self: design_control):
        fill_width = self.get_fill_width()
        x_shift = (self.bitcell_array.cell.get_pin("BL").rx() + self.line_end_space +
                   0.5 * self.m4_width + self.via_enclose)
        for name in ["en", "en_bar"]:
            pin_name = "write_" + name
            dest_pin = self.write_driver_array_inst.get_pin(name)
            for source_pin in self.get_all_control_pins(pin_name):
                m4_x_offset = self.connect_rail_to_pin(getattr(self, pin_name+"_rail"), source_pin,
                                                       dest_pin, x_shift=x_shift)

                self.add_rect("metal3", offset=vector(m4_x_offset-0.5*self.m3_width-self.via_enclose,
                                                      dest_pin.cy()-0.5*fill_width),
                              width=fill_width, height=fill_width)
                self.add_rect_center("metal4", offset=vector(m4_x_offset, dest_pin.cy()), height=m3m4.height)

                for via_layer in ["via1", "via2", "via3"]:
                    self.add_rect_center(via_layer, offset=vector(m4_x_offset, dest_pin.cy()))

                if name == "en":
                    y_offset = dest_pin.cy() + 0.5*m1m2.height - fill_width
                else:
                    y_offset = dest_pin.by()

                self.add_rect("metal2", offset=vector(m4_x_offset-0.5*fill_width, y_offset),
                              width=fill_width, height=fill_width)

    def connect_sample_b(self: design_control):
        fill_width = self.get_fill_width()

        x_shift = self.bitcell_array.cell.get_pin("BL").rx() + self.line_end_space + 0.5 * self.m4_width
        dest_pin = self.sense_amp_array_inst.get_pin("sampleb")
        vdd_pin = min(self.sense_amp_array_inst.get_pins("vdd"), key=lambda x: abs(x.cy() - dest_pin.cy()))
        en_pin = self.sense_amp_array_inst.get_pin("en")

        for source_pin in self.get_all_control_pins("sample_en_bar"):
            m4_x_offset = self.connect_rail_to_pin(self.sample_en_bar_rail, source_pin,
                                                   en_pin,
                                                   x_shift=x_shift)

            cell_mid = m4_x_offset - x_shift + 0.5 * self.bitcell.width - 0.5*self.m4_width
            cell_start = m4_x_offset - x_shift

            dout_pin = self.sense_amp_array_inst.get_pin("data[0]")

            y_bend = dout_pin.uy() + self.line_end_space + m3m4.height

            # avoid coupling to and_pin and bl by going to the middle

            self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m2_width, en_pin.cy()),
                          height=y_bend - en_pin.cy())

            self.add_rect("metal4", offset=vector(m4_x_offset - 0.5 * self.m4_width, y_bend),
                          width=cell_mid - m4_x_offset + 0.5*self.m4_width)

            self.add_rect("metal4", offset=vector(cell_mid, y_bend), height=vdd_pin.cy()-y_bend)
            self.add_contact_center(m3m4.layer_stack, offset=vector(cell_mid+0.5*self.m4_width,
                                                                    vdd_pin.cy()))

            # go to beginning of cell

            self.add_rect("metal3", offset=vector(cell_start, vdd_pin.cy()-0.5*self.m3_width),
                          width=cell_mid-cell_start)
            self.add_contact_center(m2m3.layer_stack, offset=vector(cell_start, vdd_pin.cy()))

            # go down to sampleb pin

            fill_width = m1m2.height
            fill_height = utils.ceil(self.minarea_metal1_contact/fill_width)
            self.add_rect("metal2", offset=vector(cell_start-0.5*fill_width, dest_pin.by()),
                          height=fill_height, width=fill_width)
            self.add_contact_center(m1m2.layer_stack, offset=vector(cell_start, dest_pin.cy()), rotate=90)

    def connect_precharge_bar(self: design_control):
        fill_width = self.get_fill_width()

        x_shift = self.bitcell_array.cell.get_pin("BL").rx() + self.line_end_space + 0.5 * self.m4_width
        # connect to sense_amp precharge
        for source_pin in self.get_all_control_pins("precharge_en_bar"):
            dest_pin = self.sense_amp_array_inst.get_pin("preb")
            m4_x_offset = self.connect_rail_to_pin(self.precharge_en_bar_rail, source_pin,
                                                   dest_pin, x_shift=x_shift)
            offset = vector(m4_x_offset, dest_pin.cy())

            self.add_rect_center("via3", offset=offset)
            self.add_rect_center("metal4", offset=offset, height=m3m4.height)

            height = self.line_end_space  # hack
            m2_width = fill_width * fill_width / height
            self.add_rect_center("metal2", offset=offset, width=m2_width, height=height)

            offset = vector(m4_x_offset-0.5*fill_width + self.via_enclose - 0.5*self.m2_width, dest_pin.cy())
            self.add_rect_center("via2", offset=offset)
            self.add_rect_center("via1", offset=offset)

            y_offset = dest_pin.cy() + 0.5 * m3m4.width + self.via_enclose - fill_width
            x_offset = m4_x_offset - 0.5*m2_width - self.via_enclose
            width = m4_x_offset + 0.5*self.m3_width + 0.5*self.m3_width - x_offset
            self.add_rect("metal3", offset=vector(x_offset, y_offset), width=width,
                          height=fill_width)

            # connect to precharge_en
            dest_pin = self.precharge_array_inst.get_pin("en")
            m4_x_offset = self.connect_rail_to_pin(self.precharge_en_bar_rail, source_pin,
                                                   dest_pin, x_shift=x_shift)
            # go to middle of cell
            # go to middle between precharge and bitcells

            y_offset = self.precharge_array_inst.uy()
            cell_mid = m4_x_offset - x_shift + 0.5*self.bitcell.width
            x_offset = m4_x_offset-0.5*self.m4_width
            self.add_rect("metal4", offset=vector(x_offset, y_offset), width=cell_mid-x_offset)
            self.add_rect("metal4", offset=vector(x_offset, dest_pin.cy()),
                          height=y_offset-dest_pin.cy())
            via_offset = vector(cell_mid, y_offset)
            self.add_contact_center(m3m4.layer_stack, offset=via_offset)
            self.add_contact_center(m2m3.layer_stack, offset=via_offset)
            self.add_contact_center(m1m2.layer_stack, offset=via_offset)
            self.add_rect_center("metal3", offset=via_offset, width=fill_width, height=fill_width)
            self.add_rect_center("metal2", offset=via_offset, width=fill_width, height=fill_width)
            self.add_rect("metal1", offset=vector(cell_mid-0.5*self.m1_width, dest_pin.cy()),
                          height=y_offset-dest_pin.cy())
