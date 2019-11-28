import debug
from base import design, utils
from base.contact import contact, m1m2, poly as poly_contact
from base.vector import vector
from globals import OPTS
from modules import body_tap as mod_body_tap
from pgates.ptx_spice import ptx_spice
from tech import drc, parameter


class SfBitlineBuffer(design.design):
    """
    Bitline driver buffers, should be a cascade of two inverters
    """

    def __init__(self):

        design.design.__init__(self, "SfBitlineBuffer")
        debug.info(1, "Creating {0}".format(self.name))

        self.buffer_sizes = OPTS.bitline_buffer_sizes  # type: list[int]

        self.tx_widths = [self.buffer_sizes[0] * drc["minwidth_tx"],
                          self.buffer_sizes[0] * drc["minwidth_tx"] * parameter["beta"],
                          self.buffer_sizes[1] * drc["minwidth_tx"],
                          self.buffer_sizes[1] * drc["minwidth_tx"] * parameter["beta"]]

        self.add_pins()
        self.create_layout()
        self.create_netlist()

    def create_layout(self):
        self.calculate_offsets()
        self.create_bottom_inverter()
        self.add_top_inverter()

    def create_netlist(self):
        connections = [("bl_inv", "bl_in", "gnd", "gnd"),
                       ("br_inv", "br_in", "gnd", "gnd"),
                       ("bl_inv", "bl_in", "vdd", "vdd"),
                       ("br_inv", "br_in", "vdd", "vdd"),
                       ("bl_out", "bl_inv", "gnd", "gnd"),
                       ("br_out", "br_inv", "gnd", "gnd"),
                       ("bl_out", "bl_inv", "vdd", "vdd"),
                       ("br_out", "br_inv", "vdd", "vdd")
                       ]
        tx_widths = [self.tx_widths[i] for i in [0, 0, 1, 1, 2, 2, 3, 3]]
        all_types = ["nmos", "pmos"]
        tx_types = [all_types[i % 2] for i in [0, 0, 1, 1, 2, 2, 3, 3]]
        for i in range(8):
            tx = ptx_spice(width=tx_widths[i], tx_type=tx_types[i])
            self.add_mod(tx)
            self.add_inst("ptx_{}".format(i), mod=tx, offset=vector(0, 0))
            self.connect_inst(connections[i])

    def calculate_offsets(self):
        # poly x positions
        self.poly_positions = [x * self.poly_pitch for x in range(4)]
        self.poly_left_positions = [x - 0.5 * self.poly_width for x in self.poly_positions]
        self.poly_rects = ["po_dummy", "poly", "poly", "po_dummy"]

        self.width = self.poly_positions[-1]
        self.mid_x = 0.5 * self.width

        active_enclose_contact = drc["active_enclosure_contact"]
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate
        self.active_width = 2 * self.end_to_poly + 2 * self.poly_pitch - self.poly_space

        active_contact_x_start = self.mid_x - 0.5 * self.active_width + active_enclose_contact
        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        self.active_contact_positions = [0.5 * self.contact_width + active_contact_x_start + i * self.contact_pitch for
                                         i in range(3)]

        self.implant_x = self.mid_x - 0.5 * self.active_width - self.implant_enclose_ptx_active
        
    def create_bottom_inverter(self):
        y_offset = 0

        # add poly contacts
        for x_offset in self.poly_left_positions[1:3]:
            self.add_contact(poly_contact.layer_stack,
                             offset=vector(
                                 x_offset - 0.5 * (poly_contact.second_layer_width - poly_contact.first_layer_width),
                                 y_offset))
        # min m1 drc
        x_start = 0.5 * self.parallel_line_space
        x_end = self.mid_x - 0.5 * self.parallel_line_space
        # poly extension past m1
        poly_extension = 0.5 * (poly_contact.first_layer_height - poly_contact.second_layer_height)
        width, height = self.calculate_min_m1_area(x_end - x_start, poly_contact.second_layer_height + poly_extension)
        self.add_rect("metal1", vector(x_end - width, 0), width=width, height=height)
        self.add_rect("metal1", vector(self.mid_x + 0.5 * self.parallel_line_space, 0), width=width, height=height)
        y_offset = height

        # input pins
        pin_names = ["bl_in", "br_in"]
        x_offsets = self.poly_positions[1:3]
        for i in range(2):
            self.add_layout_pin(pin_names[i], "metal1", offset=vector(x_offsets[i] - 0.5 * self.m1_width, 0),
                                height=height)

        # add nmos active
        active_height = self.tx_widths[0]

        # gnd_contact_width = drc["metal1_to_metal1_line_end"]
        gnd_contact_width = self.m1_width
        x_end = self.mid_x - 0.5 * gnd_contact_width - self.m1_space
        drain_contact_width = x_end - x_start
        (_, drain_contact_height) = self.calculate_min_m1_area(drain_contact_width, 0)
        if 0.5 * (active_height - drain_contact_height) > self.m1_space:
            active_mid_y = y_offset + 0.5 * active_height
        else:
            active_mid_y = y_offset + 0.5 * drain_contact_height + self.m1_space
        self.add_rect_center("active", offset=vector(self.mid_x, active_mid_y), width=self.active_width,
                             height=active_height)

        # add active contacts
        for i in range(3):
            self.add_rect_center("contact", offset=vector(self.active_contact_positions[i], active_mid_y))

        # fill m1 area
        fill_x_pos = [x_start, self.width - x_start - drain_contact_width]
        for i in range(2):
            self.add_rect("metal1", offset=vector(fill_x_pos[i], active_mid_y - 0.5 * drain_contact_height),
                          width=drain_contact_width, height=drain_contact_height)

        # add ground pin across
        y_offset = active_mid_y + 0.5 * drain_contact_height
        pin_base = y_offset + self.m1_space
        gnd_pin = self.add_layout_pin("gnd", "metal1", offset=vector(0, pin_base), width=self.width,
                                      height=self.rail_height)
        rect_base = active_mid_y - 0.5 * self.contact_width - drc["metal1_extend_contact"]
        rect_height = pin_base - rect_base
        self.add_rect_center("metal1", offset=vector(self.mid_x, rect_base + 0.5 * rect_height), height=rect_height)

        # add pmos active
        active_space = 2 * drc["implant_to_channel"]
        pmos_active_height = self.tx_widths[1]
        self.pmos_mid_y = pmos_mid_y = max(gnd_pin.uy() + self.m1_space + 0.5 * drain_contact_height,
                                           active_mid_y + 0.5 * active_height + active_space + 0.5 * pmos_active_height)
        self.add_rect_center("active", offset=vector(self.mid_x, pmos_mid_y), width=self.active_width,
                             height=pmos_active_height)

        # active contacts
        for i in range(3):
            self.add_rect_center("contact", offset=vector(self.active_contact_positions[i], pmos_mid_y))
        for i in range(2):
            self.add_rect("metal1", offset=vector(fill_x_pos[i], pmos_mid_y - 0.5 * drain_contact_height),
                          width=drain_contact_width, height=drain_contact_height)

        # add poly
        poly_top = pmos_mid_y + 0.5 * pmos_active_height + self.poly_extend_active
        for i in range(4):
            self.add_rect(self.poly_rects[i], offset=vector(self.poly_left_positions[i], 0), height=poly_top,
                          width=self.poly_width)

        # vdd pin
        vdd_y = pmos_mid_y + 0.5 * drain_contact_height + self.m1_space
        vdd_pin = self.add_layout_pin("vdd", "metal1", offset=vector(0, vdd_y), width=self.width,
                                      height=self.rail_height)
        rect_base = pmos_mid_y - 0.5 * self.contact_width - drc["metal1_extend_contact"]
        rect_height = vdd_pin.uy() - rect_base
        self.add_rect_center("metal1", offset=vector(self.mid_x, rect_base + 0.5 * rect_height), height=rect_height)

        # connect drains
        for x_offset in self.active_contact_positions[0:3:2]:
            for y_offset in [active_mid_y, pmos_mid_y]:
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, y_offset))
            self.add_rect("metal2", offset=vector(x_offset - 0.5 * self.m2_width, active_mid_y),
                          height=pmos_mid_y - active_mid_y)

        # add implants and nwell
        mid_y = active_mid_y + 0.5 * active_height + 0.5 * active_space

        implant_y = -self.implant_enclose_poly
        self.add_rect("nimplant", offset=vector(self.implant_x, implant_y), width=self.width - 2 * self.implant_x,
                      height=mid_y - implant_y)

        self.add_rect("pimplant", offset=vector(self.implant_x, mid_y), width=self.width - 2 * self.implant_x,
                      height=poly_top - implant_y - mid_y)
        
        self.add_rect("nwell", offset=vector(self.implant_x, mid_y), width=self.width - 2 * self.implant_x,
                      height=poly_top - implant_y - mid_y)

        self.bot_nwell = mid_y

        # variables used in top inverter
        self.bottom_poly_top = poly_top
        self.bottom_vdd_pin = vdd_pin
        self.bottom_nmos_mid_y = active_mid_y
        self.bottom_pmos_mid_y = pmos_mid_y

    def add_top_inverter(self):
        contact_y_offset = max(self.bottom_poly_top + self.poly_to_field_poly,
                               self.bottom_vdd_pin.uy() + self.m1_space -
                               0.5 * (poly_contact.first_layer_height - poly_contact.second_layer_height))
        # add poly contacts
        for x_offset in self.poly_left_positions[1:3]:
            contact_x = x_offset - 0.5 * (poly_contact.second_layer_width - poly_contact.first_layer_width)
            self.add_contact(poly_contact.layer_stack, offset=vector(contact_x, contact_y_offset))

        x_start = 0.5 * self.parallel_line_space
        x_end = self.mid_x - 0.5 * self.parallel_line_space
        fill_width, fill_height = self.calculate_min_m1_area(x_end - x_start, poly_contact.second_layer_height)
        fill_y_offset = contact_y_offset + 0.5 * (poly_contact.first_layer_height - poly_contact.second_layer_height)
        self.add_rect("metal1", vector(x_end - fill_width, fill_y_offset), width=fill_width, height=fill_height)
        self.add_rect("metal1", vector(self.mid_x + 0.5 * self.parallel_line_space, fill_y_offset),
                      width=fill_width, height=fill_height)

        # connect poly contacts
        for x_offset in self.active_contact_positions[0:3:2]:
            via_x = x_offset - 0.5 * self.m2_width
            self.add_rect("metal2", offset=vector(via_x, self.bottom_pmos_mid_y),
                          height=fill_y_offset - self.bottom_pmos_mid_y)
            self.add_via(m1m2.layer_stack, offset=vector(via_x, fill_y_offset))
        # add pmos active
        # assumes second stage is bigger than first state so m1 fill to poly contact space concerns
        co_rect_top = contact_y_offset + 0.5 * poly_contact.height + 0.5 * self.contact_width
        pmos_base = co_rect_top + drc["poly_contact_to_active"]
        pmos_height = self.tx_widths[3]
        pmos_mid_y = pmos_base + 0.5 * pmos_height
        self.add_rect_center("active", offset=vector(self.mid_x, pmos_mid_y), width=self.active_width,
                             height=pmos_height)

        m1_fill_active_overlap = fill_y_offset + fill_height - pmos_base
        extra_space = m1_fill_active_overlap + self.line_end_space + self.m1_space
        num_contacts = self.calculate_num_contacts(pmos_height - extra_space)
        contacts_y = (0.5 * (pmos_base + m1_fill_active_overlap + self.line_end_space) +
                      0.5 * (pmos_base + pmos_height - self.m1_space))
        via = None
        for i in range(3):
            pmos_via = self.add_via_center(layers=contact.active_layers,
                                           offset=vector(self.active_contact_positions[i], contacts_y),
                                           size=[1, num_contacts])

        # middle contact to vdd
        x_offset = self.active_contact_positions[1] - 0.5 * self.m2_width
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset, pmos_via.by()))
        y_offset = self.pmos_mid_y - 0.5 * m1m2.second_layer_height
        self.add_rect("metal2", offset=vector(x_offset, y_offset), height=pmos_via.by() - y_offset)
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset, y_offset), size=[1, 2])

        # top gnd pin
        pin_y = pmos_base + pmos_height
        gnd_pin = self.add_layout_pin("gnd", "metal1", offset=vector(0, pin_y), width=self.width,
                                      height=self.rail_height)

        # nmos active
        active_space = 2 * drc["implant_to_channel"]
        nmos_height = self.tx_widths[2]
        nmos_base = pmos_base + pmos_height + active_space
        nmos_mid_y = nmos_base + 0.5 * nmos_height
        self.add_rect_center("active", offset=vector(self.mid_x, nmos_mid_y), width=self.active_width,
                             height=nmos_height)
        # nmos active contacts
        extra_space = self.line_end_space + self.rail_height - active_space
        num_contacts = self.calculate_num_contacts(nmos_height - extra_space)
        contacts_y = 0.5 * (nmos_base + nmos_height) + 0.5 * (nmos_base + extra_space)
        nmos_via = None
        for i in range(3):
            nmos_via = self.add_via_center(layers=contact.active_layers,
                                           offset=vector(self.active_contact_positions[i], contacts_y),
                                           size=[1, num_contacts])
        # connect drains
        for x_offset in self.active_contact_positions[0:3:2]:
            via_x = x_offset - 0.5 * self.m2_width
            self.add_rect("metal2", offset=vector(via_x, pmos_via.uy()), height=nmos_via.by() - pmos_via.uy())
            self.add_via(m1m2.layer_stack, offset=vector(via_x, pmos_via.uy() - m1m2.second_layer_height))
            self.add_via(m1m2.layer_stack, offset=vector(via_x, nmos_via.by()))
        # middle contact to gnd
        x_offset = self.active_contact_positions[1] - 0.5 * self.m2_width
        self.add_rect("metal1", offset=vector(x_offset, gnd_pin.uy()),
                      height=nmos_via.by() - gnd_pin.uy())
        # add poly
        poly_top = nmos_base + nmos_height + self.poly_extend_active
        for i in range(4):
            self.add_rect(self.poly_rects[i], offset=vector(self.poly_left_positions[i], contact_y_offset),
                          height=poly_top - contact_y_offset, width=self.poly_width)

        # pimplants
        y_offset = self.bottom_vdd_pin.uy()
        implant_top = nmos_base - drc["implant_to_channel"]
        self.add_rect("pimplant", offset=vector(self.implant_x, y_offset), width=self.width - 2 * self.implant_x,
                      height=implant_top - y_offset)
        
        self.add_rect("nwell", offset=vector(self.implant_x, y_offset), width=self.width - 2 * self.implant_x,
                      height=implant_top - y_offset)
        self.top_nwell = implant_top

        # nimplant
        self.add_rect("nimplant", offset=vector(self.implant_x, implant_top), width=self.width - 2 * self.implant_x,
                      height=poly_top + self.implant_enclose_poly - implant_top)

        # leave poly space from bitcell poly
        c = __import__(OPTS.bitcell)
        bitcell = getattr(c, OPTS.bitcell)()
        bitcell_poly = self.get_gds_layer_shapes(bitcell, "poly")
        min_poly_y = min(bitcell_poly, key=lambda x: x[0][1])[0][1]
        self.height = poly_top + self.poly_to_field_poly - min_poly_y

        # output pins
        pin_names = ["bl_out", "br_out"]
        x_offsets = self.active_contact_positions[0:3:2]
        for i in range(2):
            self.add_layout_pin(pin_names[i], "metal2",
                                offset=vector(x_offsets[i] - 0.5 * self.m2_width, nmos_via.by()),
                                height=self.height - nmos_via.by())

    def add_pins(self):
        self.add_pin_list(["bl_in", "br_in", "bl_out", "br_out", "vdd", "gnd"])


class SfBitlineBufferTap(design.design):
    bitline_buffer = None

    def __init__(self, bitline_buffer):
        super().__init__("sf_bitline_buffer_tap")

        self.bitline_buffer = bitline_buffer

        self.create_layout()

    def create_layout(self):

        bitcell_tap = mod_body_tap.body_tap
        self.width = bitcell_tap.width
        self.height = self.bitline_buffer.height

        # add poly dummies
        poly_allowance = 0.5 * self.poly_to_field_poly
        x_offsets = [self.poly_space + 0.5 * self.poly_width,
                     self.width - (self.poly_space + 0.5 * self.poly_width) - self.poly_width]
        for x_offset in x_offsets:
            self.add_rect("po_dummy", offset=vector(x_offset, poly_allowance),
                          height=self.height - 2 * poly_allowance, width=self.poly_width)

        # fill nwell
        top_well = self.bitline_buffer.top_nwell
        bot_well = self.bitline_buffer.bot_nwell
        self.add_rect("nwell", offset=vector(0, bot_well), width=self.width, height=top_well - bot_well)

        

        vdd_pin = self.bitline_buffer.get_pin("vdd")
        dummy_space = x_offsets[1] - x_offsets[0] - self.poly_width  # space between poly
        active_width = dummy_space - 2 * self.poly_to_active
        active_height = utils.ceil(drc["minarea_cont_active_thin"] / active_width)

        # add nwell contact

        self.add_rect_center("active", offset=vector(0.5 * self.width, vdd_pin.cy()), width=active_width,
                             height=active_height)

        implant_width = self.width + 2 * self.bitline_buffer.implant_x
        implant_height = max(active_height + 2 * self.implant_enclose_active,
                             utils.ceil(drc["minarea_cont_active_thin"] / implant_width))

        self.add_rect_center("nimplant", offset=vector(0.5 * self.width, vdd_pin.cy()), width=implant_width,
                             height=implant_height)

        num_contacts = self.calculate_num_contacts(active_height)
        self.add_contact_center(contact.active_layers, offset=vector(0.5 * self.width, vdd_pin.cy()),
                                size=[1, num_contacts])
        # psub contact
        self.add_psub_contacts(implant_height, implant_width, active_height, active_width, num_contacts)

        # fill pins
        pin_names = ["vdd", "gnd"]
        for pin_name in pin_names:
            for pin in self.bitline_buffer.get_pins(pin_name):
                self.add_rect(pin.layer, offset=vector(0, pin.by()), width=self.width, height=pin.height())

    def add_psub_contacts(self, implant_height, implant_width, active_height, active_width, num_contacts):
        bottom_nimplant = min(self.bitline_buffer.get_layer_shapes("nimplant"), key=lambda x: x.by())
        implant_top = bottom_nimplant.uy() - self.implant_space
        implant_bottom = implant_top - implant_height
        implant_x = 0.5 * (self.width - implant_width)
        self.add_rect("pimplant", offset=vector(implant_x, implant_bottom), width=implant_width, height=implant_height)

        center_y = implant_bottom + 0.5 * implant_height
        self.add_rect_center("active", offset=vector(0.5 * self.width, center_y),
                             width=active_width, height=active_height)

        cont = self.add_contact_center(contact.active_layers, offset=vector(0.5 * self.width, center_y),
                                       size=[1, num_contacts])
        gnd_pin = min(self.bitline_buffer.get_pins("gnd"), key=lambda x: x.by())
        self.add_rect("metal1", offset=vector(0.5 * self.width - 0.5 * gnd_pin.height(), cont.by()),
                      width=gnd_pin.height(), height=gnd_pin.by() - cont.by())
