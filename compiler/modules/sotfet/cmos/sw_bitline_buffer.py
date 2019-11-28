import debug
from base import utils
from base.contact import m1m2, m2m3, contact
from base.design import design
from base.vector import vector
from globals import OPTS
from modules.sotfet.sf_bitline_buffer import SfBitlineBufferTap
from pgates.pinv_bitline_buffer import pinv_bitine_buffer
from tech import drc


class SwBitlineBufferTap(SfBitlineBufferTap):
    def __init__(self, bitline_buffer):
        design.__init__(self, "sw_bitline_buffer_tap")
        self.bitline_buffer = bitline_buffer  # type: SwBitlineBuffer

        self.create_layout()

    def add_psub_contacts(self, implant_height, implant_width, active_height, active_width, num_contacts):
        implant_space = self.implant_space
        offsets = [self.bitline_buffer.bot_nwell - implant_space - 0.5*implant_height,
                   self.bitline_buffer.top_nwell + implant_space + 0.5*implant_height]

        for i in range(2):
            offset = vector(0.5*self.width, offsets[i])
            self.add_rect_center("pimplant", offset=offset,
                                 width=implant_width, height=implant_height)
            self.add_rect_center("active", offset=offset, width=active_width, height=active_height)

            cont = self.add_contact_center(contact.active_layers, offset=offset, size=[1, num_contacts])
            gnd_pin = min(self.bitline_buffer.get_pins("gnd"), key=lambda x: abs(x.cy() - offset.y))

            top_y = max(gnd_pin.cy(), offset.y + 0.5*cont.mod.second_layer_height)
            bot_y = min(gnd_pin.cy(), offset.y - 0.5*cont.mod.second_layer_height)
            mid_y = 0.5*(top_y + bot_y)
            self.add_rect_center("metal1", offset=vector(offset.x, mid_y),
                                 width=gnd_pin.height(), height=top_y-bot_y)


class SwBitlineBuffer(design):
    def __init__(self):
        design.__init__(self, "SwBitlineBuffer")
        debug.info(1, "Creating {0}".format(self.name))

        self.buffer_sizes = OPTS.bitline_buffer_sizes  # type: list[int]

        self.create_modules()

        self.width = self.in_buffer.bitcell.width

        self.add_modules()

        self.height = self.out_bl_buf.uy()

        self.add_pins()

        self.route_layout()

        self.set_tap_properties()

        self.add_dummy()

        # self.body_tap = SwBitlineBufferTap(self)
        # self.add_mod(self.body_tap)
        # self.add_inst("tap", mod=self.body_tap, offset=vector(self.width, 0))
        # self.connect_inst([])

    def create_modules(self):
        self.in_buffer = pinv_bitine_buffer(size=self.buffer_sizes[0], contact_pwell=False,
                                            contact_nwell=False)
        self.add_mod(self.in_buffer)
        self.out_buffer = pinv_bitine_buffer(size=self.buffer_sizes[1], contact_pwell=False,
                                             contact_nwell=False)
        self.add_mod(self.out_buffer)

    def add_modules(self):

        bl_offset = -self.in_buffer.dummy_x
        br_offset = self.width + self.in_buffer.dummy_x
        y_offset = 0
        self.in_bl_buf = self.add_inst("in_bl_buf", mod=self.in_buffer,
                                       offset=vector(bl_offset, y_offset))
        self.connect_inst(["bl_in", "bl_inv", "vdd", "gnd"])

        self.in_br_buf = self.add_inst("in_br_buf", mod=self.in_buffer,
                                       offset=vector(br_offset, y_offset), mirror="MY")
        self.connect_inst(["br_in", "br_inv", "vdd", "gnd"])

        y_offset = self.in_buffer.height + self.out_buffer.height
        self.out_bl_buf = self.add_inst("out_bl_buf", mod=self.out_buffer,
                                        offset=vector(bl_offset, y_offset), mirror="MX")
        self.connect_inst(["bl_inv", "bl_out", "vdd", "gnd"])

        self.out_br_buf = self.add_inst("out_br_buf", mod=self.out_buffer,
                                        offset=vector(br_offset, y_offset), mirror="XY")
        self.connect_inst(["br_inv", "br_out", "vdd", "gnd"])

    def route_layout(self):
        bl_offset = 0.5*self.parallel_via_space
        br_offset = self.width - 0.5*self.parallel_via_space - self.m2_width

        offsets = [bl_offset, br_offset]
        in_buffers = [self.in_bl_buf, self.in_br_buf]
        out_buffers = [self.out_bl_buf, self.out_br_buf]
        in_pin_names = ["bl_in", "br_in"]
        out_pin_names = ["bl_out", "br_out"]
        bitcell_pins = [self.in_buffer.bitcell.get_pin("BL"),
                        self.in_buffer.bitcell.get_pin("BR")]
        for i in range(2):
            # input pins
            in_buffer = in_buffers[i]
            out_buffer = out_buffers[i]

            a_pin = in_buffer.get_pin("A")
            self.add_contact_center(m1m2.layer_stack, offset=a_pin.center(), rotate=90)
            self.add_contact_center(m2m3.layer_stack, offset=a_pin.center(), rotate=90)

            fill_width = 0.5*m1m2.height + 0.5*a_pin.width()
            fill_height = utils.ceil(drc["minarea_metal1_contact"]/fill_width)
            if i == 0:
                fill_x = a_pin.cx() - 0.5*m1m2.height
            else:
                fill_x = a_pin.cx() + 0.5*m1m2.height - fill_width
            self.add_rect("metal2", offset=vector(fill_x, a_pin.cy() - 0.5*fill_height),
                          width=fill_width, height=fill_height)

            self.add_layout_pin(in_pin_names[i], "metal3",
                                offset=vector(a_pin.cx()-0.5*self.m3_width, 0), height=a_pin.cy())

            # in_inv to out_in
            x_offset = offsets[i]
            z_pins = in_buffer.get_pins("Z")
            a_pin = out_buffer.get_pin("A")

            for pin in z_pins:
                self.add_rect("metal2", offset=vector(x_offset, pin.by()),
                              width=pin.lx()-x_offset)
                self.add_rect("metal2", offset=vector(x_offset, pin.by()),
                              height=a_pin.cy()-pin.by())
            offset = vector(x_offset, a_pin.cy()-0.5*m1m2.height)
            self.add_contact(m1m2.layer_stack, offset=offset)
            right_x = a_pin.lx() if i == 0 else a_pin.rx() - self.m1_width
            self.add_rect("metal1", offset=offset, height=m1m2.height, width=right_x-x_offset)

            # output pin
            z_pins = out_buffer.get_pins("Z")
            self.add_rect("metal2", offset=z_pins[0].lc(), height=z_pins[1].cy()-z_pins[0].cy())
            top_z_pin = max(z_pins, key=lambda x: x.uy())

            offset = vector(bitcell_pins[i].lx(), top_z_pin.by())
            self.add_rect("metal2", offset=offset, width=top_z_pin.lx()-offset.x)
            self.add_layout_pin(out_pin_names[i], "metal2", offset=offset, height=self.height-offset.y)

        self.copy_layout_pin(self.in_bl_buf, "vdd", "vdd")
        self.copy_layout_pin(self.in_bl_buf, "gnd", "gnd")
        self.copy_layout_pin(self.out_bl_buf, "gnd", "gnd")

    def add_dummy(self):
        height = self.height - self.poly_to_field_poly
        for x_offset in [0, self.width]:
            self.add_rect_center("po_dummy", vector(x_offset, 0.5*self.height), height=height, width=self.poly_width)

    def add_pins(self):
        self.add_pin_list(["bl_in", "br_in", "bl_out", "br_out", "vdd", "gnd"])

    def set_tap_properties(self):
        top_buffer = self.out_bl_buf
        bottom_buffer = self.in_bl_buf
        self.top_nwell = top_buffer.by() + (top_buffer.mod.height - top_buffer.mod.mid_y)
        self.bot_nwell = bottom_buffer.mod.mid_y
        nimplant = bottom_buffer.mod.get_layer_shapes("nimplant")[0]
        self.implant_x = bottom_buffer.lx() + nimplant.offset.x
