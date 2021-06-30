from typing import Union

from base import utils
from base.contact import m3m4, m2m3, m1m2
from base.design import design
from base.geometry import rectangle
from base.pin_layout import pin_layout
from base.vector import vector
from modules.control_buffers_repeaters_mixin import ControlBuffersRepeatersMixin
from tech import drc

design_control = Union[design, 'BlControlBuffersMixin']

class BlControlBuffersRepeatersMixin(ControlBuffersRepeatersMixin):
    def connect_buffer_rails(self: design_control):
        if self.mirror_sense_amp:
            return

        self.repeaters_dict = {}
        self.create_buffer_modules()

        self.via_enclose = drc["wide_metal_via_extension"]
        self.connect_clk()
        self.connect_sense_en()
        self.connect_write_en()
        # self.connect_sample_b()
        self.connect_precharge_bar()
        self.connect_sense_precharge()

    def get_x_shift(self: design_control):
        return self.grid_pos[0] + self.m4_width + self.parallel_line_space + 0.5*self.m4_width

    def get_via_extension(self):
        return utils.ceil(0.5 * (m3m4.height - self.m3_width))

    def connect_rail_to_pin(self: design_control, source_rail: rectangle,
                            source_pin: pin_layout, destination_pin: pin_layout, x_shift=0.0):
        x_offset = self.find_closest_x(source_pin.rx()) + x_shift

        via_extension = self.get_via_extension()

        self.add_rect("metal3", offset=vector(source_pin.lx(), source_rail.by()),
                      width=x_offset+0.5*self.m2_width-source_pin.lx()+via_extension, height=self.m3_width)
        self.add_rect_center("via3", offset=vector(x_offset, source_rail.by()+0.5*self.m3_width))
        self.add_rect("metal4", offset=vector(x_offset-0.5*self.m4_width, source_rail.by()-via_extension),
                      height=destination_pin.cy()-source_rail.by()+via_extension)

        return x_offset

    def connect_clk(self: design_control):
        #
        via_extension = self.get_via_extension()

        # clk_buf
        source_rail = self.clk_bar_rail
        dest_pin = self.data_in_flops_inst.get_pin("clk")

        for source_pin in self.get_all_control_pins("clk_bar"):
                m4_x_offset = self.connect_rail_to_pin(source_rail, source_pin, dest_pin, self.get_x_shift())

                offset = vector(m4_x_offset, dest_pin.cy())
                self.add_rect_center("via3", offset=offset)

                self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, dest_pin.by()),
                              height=self.m4_width+via_extension)

                cell_start_x = m4_x_offset - self.get_x_shift()
                self.add_rect_center("via2", offset=vector(cell_start_x, dest_pin.cy()))
                self.add_rect_center("via1", offset=vector(cell_start_x, dest_pin.cy()))

                metal3_x = cell_start_x - 0.5*self.m3_width - via_extension
                self.add_rect("metal3", offset=vector(metal3_x, dest_pin.cy()-0.5*m3m4.height),
                                     height=m3m4.height, width=m4_x_offset+0.5*self.m3_width+via_extension-metal3_x)
                # m2 fill
                fill_height = m3m4.height
                fill_width = self.get_fill_width()**2/fill_height
                y_offset = dest_pin.cy() - 0.5*fill_height - drc["metal1_enclosure_contact"] # hack

                self.add_rect("metal2", offset=vector(cell_start_x - 0.5 * fill_width, y_offset),
                              width=fill_width, height=fill_height)

    def connect_sense_en(self: design_control):
        source_rail = self.sense_en_rail
        dest_pin = self.sense_amp_array_inst.get_pin("en")

        x_shift = self.get_x_shift()

        for source_pin in self.get_all_control_pins("sense_en"):
            # for now, only connect the rhs one
            if source_pin.cx() < dest_pin.cx():
                continue

            x_offset = self.sense_amp_array_inst.rx() + self.wide_m1_space

            self.add_rect("metal3", offset=vector(source_pin.lx(), source_rail.by()),
                          width=x_offset - source_pin.lx(), height=self.m3_width)
            self.add_contact(m3m4.layer_stack, offset=vector(x_offset, source_rail.by()))
            self.add_rect("metal4", offset=vector(x_offset, source_rail.by()),
                          height=dest_pin.cy() - source_rail.by())
            self.add_contact_center(m3m4.layer_stack, offset=vector(x_offset+0.5*self.m4_width, dest_pin.cy()))
            self.add_rect("metal3", offset=dest_pin.lr(), width=x_offset-dest_pin.rx())

    def connect_write_en(self: design_control):
        fill_width = self.get_fill_width()
        x_shift = self.get_x_shift()
        via_extension = self.get_via_extension()
        for name in ["en", "en_bar"]:
            pin_name = "write_" + name
            dest_pin = self.write_driver_array_inst.get_pin(name)
            for source_pin in self.get_all_control_pins(pin_name):
                m4_x_offset = self.connect_rail_to_pin(getattr(self, pin_name + "_rail"), source_pin,
                                                       dest_pin, x_shift=x_shift)

                x_offset = m4_x_offset + self.m3_width
                self.add_via_center(m3m4.layer_stack, offset=vector(x_offset, dest_pin.cy()))
                self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, dest_pin.cy()-0.5*m3m4.height),
                              height=m3m4.height, width=self.via_enclose+x_offset+0.5*self.m4_width-
                                                        (m4_x_offset-0.5*self.m4_width))
                m3_fill_width = 2*via_extension + m3m4.width
                m3_fill_height = fill_width**2/m3_fill_width
                self.add_rect_center("metal3", offset=vector(x_offset, dest_pin.cy()), width=m3_fill_width,
                                     height=m3_fill_height)

                self.add_via_center(m2m3.layer_stack, offset=vector(x_offset, dest_pin.cy()), rotate=90)
                self.add_via_center(m1m2.layer_stack, offset=vector(x_offset, dest_pin.cy()), rotate=90)
                if name == "en":
                    y_offset = dest_pin.cy() + 0.5*m1m2.height - fill_width
                else:
                    y_offset = dest_pin.by()

                self.add_rect("metal2", offset=vector(x_offset-0.5*fill_width, y_offset),
                              width=fill_width, height=fill_width)

    def connect_sample_b(self: design_control):
        x_shift = self.get_x_shift()
        via_enclose = self.via_enclose
        fill_width = self.get_fill_width()
        bottom_pin = min(self.sense_amp_array_inst.get_pins("sampleb"), key=lambda x: x.by())
        top_pin = max(self.sense_amp_array_inst.get_pins("sampleb"), key=lambda x: x.by())
        for source_pin in self.get_all_control_pins("sample_en_bar"):
            m4_x_offset = self.connect_rail_to_pin(self.sample_en_bar_rail, source_pin,
                                                   bottom_pin, x_shift=x_shift)
            self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, bottom_pin.cy()))

            x_offset = m4_x_offset + self.m2_width

            self.add_rect_center("via2", offset=vector(x_offset, bottom_pin.cy()))
            self.add_rect_center("via1", offset=vector(x_offset, bottom_pin.cy()))

            m2_fill_width = fill_width
            m2_fill_height = fill_width
            self.add_rect("metal2", offset=vector(m4_x_offset,
                                                  bottom_pin.uy() + via_enclose - m2_fill_height),
                          height=m2_fill_height, width=m2_fill_width)
            m3_fill_width = x_offset + self.m3_width - m4_x_offset + 0.5*self.m4_width + 2*via_enclose
            m3_fill_height = fill_width**2/m3_fill_width
            self.add_rect("metal3", offset=vector(m4_x_offset-self.via_enclose-0.5*self.m4_width,
                                                  bottom_pin.cy()-0.5*m3_fill_height),
                          width=m3_fill_width, height=m3_fill_height)

            # find clearance to go across cell through m3

            clearances = utils.get_clearances(self.sense_amp_array.amp, "metal3")
            half_height = 0.5*self.sense_amp_array.amp.height
            max_clearance = max(filter(lambda x: x[0] > half_height, clearances), key=lambda x: x[1]-x[0])

            mid_y = 0.5*(max_clearance[0] + max_clearance[1]) + self.sense_amp_array_inst.by()
            self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, bottom_pin.cy()),
                          height=mid_y-bottom_pin.cy())

            cell_start = m4_x_offset - x_shift

            x_offset = cell_start + self.grid_pos[-2] - self.m4_width
            self.add_contact_center(m3m4.layer_stack, offset=vector(m4_x_offset, mid_y))
            self.add_rect("metal3", offset=vector(m4_x_offset-0.5*self.m4_width, mid_y-0.5*self.m3_width),
                          width=x_offset-m4_x_offset+0.5*self.m4_width)
            self.add_contact_center(m3m4.layer_stack, offset=vector(x_offset+0.5*self.m4_width, mid_y))

            self.add_rect("metal4", offset=vector(x_offset, mid_y), height=top_pin.cy()-mid_y+0.5*m3m4.height)

            via_x = x_offset + self.m4_width
            self.add_contact_center(m3m4.layer_stack, offset=vector(via_x, top_pin.cy()))
            # extend via
            self.add_rect("metal4", offset=vector(via_x, top_pin.cy() - 0.5 * m3m4.height),
                          width=0.5*m3m4.width+via_enclose, height=m3m4.height)

            m3_fill_height = m3m4.height
            m3_fill_width = fill_width*fill_width/m3_fill_height
            self.add_rect("metal3", offset=vector(x_offset, top_pin.cy()-0.5*m3_fill_height),
                          height=m3_fill_height, width=m3_fill_width)

            via_x = x_offset + self.m4_width + via_enclose
            self.add_contact_center(m2m3.layer_stack, offset=vector(via_x, top_pin.cy()))
            self.add_contact_center(m2m3.layer_stack, offset=vector(via_x, top_pin.cy()), rotate=90)

            m2_fill_height = m2m3.height
            m2_fill_width = fill_width*fill_width/m2_fill_height
            m2_x_offset = via_x + 0.5*m2m3.height - m2_fill_width
            self.add_rect("metal2", offset=vector(m2_x_offset, top_pin.cy()-0.5*m2_fill_height),
                          width=m2_fill_width, height=m2_fill_height)

    def connect_precharge_bar(self: design_control):
        fill_width = self.get_fill_width()

        x_shift = self.get_x_shift()
        # connect to sense_amp precharge
        for source_pin in self.get_all_control_pins("precharge_en_bar"):
            # connect to precharge_en

            dest_pin = self.precharge_array_inst.get_pin("en")

            m4_x_offset = self.connect_rail_to_pin(self.precharge_en_bar_rail, source_pin,
                                                   dest_pin, x_shift=x_shift)

            cell_mid = m4_x_offset - x_shift + 0.5 * self.bitcell.width

            y_bend = dest_pin.uy() - self.line_end_space - m3m4.height
            self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, self.precharge_en_bar_rail.by()),
                          height=y_bend-self.precharge_en_bar_rail.by())
            self.add_contact(m3m4.layer_stack, offset=vector(m4_x_offset-0.5*self.m4_width, y_bend-m3m4.height))

            # go to middle of cell
            # go to middle between precharge and bitcells

            y_offset = self.precharge_array_inst.uy()

            x_offset = m4_x_offset - 0.5*self.m3_width
            self.add_rect("metal3", offset=vector(x_offset, y_bend - self.m4_width),
                          width=cell_mid - x_offset+0.5*self.m3_width)
            self.add_rect("metal3", offset=vector(cell_mid-0.5*self.m3_width, y_bend), height=y_offset-y_bend)

            via_offset = vector(cell_mid, y_offset)

            self.add_contact_center(m2m3.layer_stack, offset=via_offset)
            self.add_contact_center(m1m2.layer_stack, offset=via_offset)
            self.add_rect_center("metal2", offset=via_offset, width=fill_width, height=fill_width)
            self.add_rect("metal1", offset=vector(cell_mid - 0.5 * self.m1_width, dest_pin.cy()),
                          height=y_offset - dest_pin.cy())

    def connect_sense_precharge(self: design_control):
        dest_pin = self.sense_amp_array_inst.get_pin("preb")
        source_pin = self.control_buffers_inst.get_pin("sense_precharge_bar")

        via_offset = source_pin.ul() - vector(-m2m3.height, self.m3_width)
        self.add_contact(m2m3.layer_stack, offset=via_offset, rotate=90)

        x_shift = self.get_x_shift()

        m4_x_offset = self.find_closest_x(source_pin.rx()) + x_shift

        self.add_rect("metal3", offset=vector(source_pin.lx(), source_pin.uy()-self.m3_width),
                      width=max(m4_x_offset - source_pin.lx(), self.minarea_metal1_minwidth/self.m3_width),
                      height=self.m3_width)

        via_y = via_offset.y + 0.5*(self.m3_width-m3m4.height)
        self.add_contact(m3m4.layer_stack, offset=vector(m4_x_offset-0.5*self.m4_width, via_y))
        self.add_rect("metal4", offset=vector(m4_x_offset-0.5*self.m4_width, via_offset.y),
                      height=dest_pin.cy()-via_offset.y)

        y_offset = dest_pin.by() - self.line_end_space - 0.5 * m3m4.height

        for via in [m3m4, m2m3]:
            self.add_contact_center(via.layer_stack, vector(m4_x_offset, y_offset))

        self.add_contact_center(m1m2.layer_stack, vector(m4_x_offset, y_offset), rotate=90)

        for layer in ["metal2", "metal3"]:
            self.add_rect_center(layer, offset=vector(m4_x_offset, y_offset), width=self.get_fill_width(),
                                 height=self.get_fill_width())

        self.add_rect("metal1", offset=vector(m4_x_offset - 0.5 * self.m1_width, y_offset),
                      height=dest_pin.by() - y_offset)
        pass


