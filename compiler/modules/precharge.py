import debug
from base import contact
from base import design
from base import utils
from base.contact import m1m2, m2m3, m3m4
from base.design import METAL2
from base.vector import vector
from globals import OPTS
from pgates.ptx_spice import ptx_spice
from tech import drc, parameter


class precharge(design.design):
    """
    Creates a single precharge cell
    This module implements the precharge bitline cell used in the design.
    """

    def __init__(self, name, size=1):
        design.design.__init__(self, name)
        debug.info(2, "create single precharge cell: {0}".format(name))

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell = self.mod_bitcell()
        
        self.beta = parameter["beta"]
        self.ptx_width = utils.round_to_grid(size*self.beta*parameter["min_tx_size"])
        self.width = self.bitcell.width

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        self.add_pin_list(["bl", "br", "en", "vdd"])

    def create_layout(self):
        self.set_layout_constants()
        self.create_ptx()
        self.connect_input_gates()
        self.add_nwell_contacts()
        self.add_active_contacts()
        self.connect_bitlines()
        self.drc_fill()
        self.add_ptx_inst()


    def set_layout_constants(self):

        self.mid_x = 0.5*self.width

        # TODO should depend on bitcell width
        self.mults = 3

        self.well_contact_implant_height = drc["minwidth_implant"]
        self.well_contact_active_height = contact.active.first_layer_height
        # nwell contact top space requirement
        nwell_top_space = (0.5*self.well_contact_implant_height + self.poly_extend_active +
                           0.5*self.well_contact_active_height + self.poly_to_active)

        # need space from top m2 joining fingers
        m2_top_space = (self.line_end_space + self.m2_width + self.m2_space + m1m2.second_layer_width
                        + 0.5*(self.well_contact_implant_height - self.well_contact_active_height))

        self.top_space = max(nwell_top_space, m2_top_space)

        poly_enclosure = drc["implant_enclosure_poly"]

        self.gate_y = poly_enclosure + 0.5*contact.poly.first_layer_height

        self.bottom_space = (self.gate_y + 0.5*contact.poly.second_layer_height +
            self.line_end_space)
        self.poly_height = (0.5*contact.poly.first_layer_height + 0.5*contact.poly.second_layer_height +
                            self.line_end_space + self.ptx_width + self.poly_extend_active)
        self.poly_y_offset = poly_enclosure


        self.height = self.bottom_space + self.ptx_width + self.top_space

        active_enclose_contact = drc["active_enclosure_contact"]
        self.poly_pitch = self.poly_width + self.poly_space
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate

        self.active_width = 2 * self.end_to_poly + self.mults * self.poly_pitch - self.poly_space
        self.active_bot_y = self.bottom_space
        self.active_mid_y = self.active_bot_y + 0.5*self.ptx_width

        self.poly_x_start = (self.mid_x - 0.5 * self.active_width +
                             self.end_to_poly - 2 * self.poly_pitch + 0.5 * self.poly_width)

        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        self.contact_space = self.contact_pitch - self.contact_width
        self.calculate_body_contacts()

        self.nwell_height = self.contact_y + 0.5*self.well_contact_active_height + drc["well_enclosure_active"]
        


        self.implant_height = self.height - self.well_contact_implant_height
        implant_enclosure_active = drc["ptx_implant_enclosure_active"]
        self.implant_width = self.width + 2 * implant_enclosure_active
        self.implant_width = max(self.implant_width,
                                 utils.ceil(self.well_contact_active_width + 2 * implant_enclosure_active),
                                 utils.ceil(drc["minarea_implant"] / self.well_contact_implant_height))






    def create_ptx(self):
        """Initializes all the pmos"""

        # add active
        self.add_rect_center("active", offset=vector(self.mid_x, self.active_mid_y),
                             width=self.active_width, height=self.ptx_width)

        # add poly
        poly_layers = 2*["po_dummy"] + ["poly"]*self.mults + 2*["po_dummy"]



        for i in range(len(poly_layers)):
            offset = vector(self.poly_x_start + i*self.poly_pitch - 0.5*self.poly_width, self.poly_y_offset)
            self.add_rect(poly_layers[i], offset=offset, height=self.poly_height, width=self.poly_width)

        # add implant
        self.add_rect_center("pimplant", offset=vector(self.mid_x, 0.5*self.implant_height),
                             width=self.implant_width, height=self.implant_height)

        # add nwell
        x_offset = - 0.5*(self.implant_width - self.width)
        self.add_rect("nwell", offset=vector(x_offset, 0), width=self.implant_width, height=self.nwell_height)

        
    def connect_input_gates(self):
        gate_pos = [self.mid_x - self.poly_pitch, self.mid_x, self.mid_x + self.poly_pitch]

        for x_offset in gate_pos:
            self.add_contact_center(layers=contact.contact.poly_layers, offset=vector(x_offset, self.gate_y))

        self.add_layout_pin_center_rect("en", "metal1", offset=vector(self.mid_x, self.gate_y),  width=self.width)

    def calculate_body_contacts(self):
        if self.mults % 2 == 0:
            no_contacts = self.mults + 1
        else:
            no_contacts = self.mults
        self.no_body_contacts = no_contacts = max(3, no_contacts)
        contact_extent = no_contacts*self.contact_pitch - self.contact_space
        self.contact_x_start = self.mid_x - 0.5*contact_extent + 0.5*self.contact_width
        min_active_width = utils.ceil(drc["minarea_cont_active_thin"] / self.well_contact_active_height)
        active_width = max(2 * contact.active.first_layer_vertical_enclosure + contact_extent,
                           min_active_width)
        # prevent minimum spacing drc
        if self.width - active_width < drc["active_to_active"]:
            active_width = max(active_width, self.width)
        self.well_contact_active_width = active_width

        self.contact_y = self.height - 0.5*self.well_contact_implant_height


    def add_nwell_contacts(self):
        self.add_rect_center("nimplant", offset=vector(self.mid_x, self.contact_y), width=self.implant_width,
                             height=self.well_contact_implant_height)
        mid_contact_y = self.contact_y
        # TODO temp fix since sense amps expect vdd rail to extend by 0.5*self.rail_height
        active_top = self.active_bot_y + self.ptx_width
        pin_height = self.contact_y + 0.5*self.rail_height - active_top - self.line_end_space
        self.add_layout_pin("vdd", "metal1", offset=vector(0, active_top + self.line_end_space),
                            width=self.width, height=pin_height)

        self.add_rect("metal3", offset=vector(0, active_top + self.line_end_space),
                      width=self.width, height=pin_height)
        via_y = self.get_pin("vdd").uy() - 0.5*m1m2.second_layer_width
        self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_x, via_y), size=[1, 3], rotate=90)
        self.add_contact_center(m2m3.layer_stack, offset=vector(self.mid_x, via_y), size=[1, 3], rotate=90)


        self.add_rect_center("active", offset=vector(self.mid_x, self.contact_y), width=self.well_contact_active_width,
                             height=self.well_contact_active_height)
        for j in range(self.no_body_contacts):
            x_offset = self.contact_x_start + j * self.contact_pitch
            self.add_rect_center("contact", offset=vector(x_offset, self.contact_y))

    def add_active_contacts(self):
        no_contacts = self.calculate_num_contacts(self.ptx_width)
        m1m2_contacts = max(1, no_contacts-1)
        active_left = self.mid_x - 0.5*self.active_width + 0.5*self.m1_width  # left edge of active layer

        self.source_drain_pos = []
        for i in range(4):
            offset = vector(active_left + i*self.poly_pitch, self.active_mid_y)
            self.source_drain_pos.append(offset.x)
            self.add_contact_center(layers=contact.contact.active_layers, size=[1, no_contacts], offset=offset)
            if i == 1:
                # connect to vdd
                mid_y = 0.5*(self.contact_y + self.active_bot_y)
                height = self.contact_y - self.active_bot_y
                offset = vector(offset.x, mid_y)
                self.add_rect_center("metal1", offset=offset, height=height)
            else:
                # add m1m2 via
                self.add_contact_center(layers=contact.contact.m1m2_layers, size=[1, m1m2_contacts], offset=offset)
                self.add_rect_center("metal1", offset=offset, height=self.ptx_width)

    def connect_bitlines(self):
        top_connection_y = self.active_bot_y + self.ptx_width + self.line_end_space
        for i in [0, 3]:
            x_offset = self.source_drain_pos[i] - 0.5*self.m2_width
            self.add_rect("metal2", offset=vector(x_offset, self.active_mid_y),
                          height=top_connection_y-self.active_mid_y + self.m2_width)
        self.add_rect("metal2", offset=vector(self.source_drain_pos[0], top_connection_y),
                      width=self.source_drain_pos[3]-self.source_drain_pos[0])

        bl_x = self.bitcell.get_pin("BL").lx()
        br_x = self.bitcell.get_pin("BR").lx()

        bottom_connection_y = self.active_bot_y - self.line_end_space
        for i in [0, 2]:
            x_offset = self.source_drain_pos[i] - 0.5*self.m2_width
            self.add_rect("metal2", offset=vector(x_offset, bottom_connection_y),
                          height=self.active_mid_y-bottom_connection_y)

        offset = vector(bl_x, bottom_connection_y-self.m2_width)
        self.add_rect("metal2", offset=offset, width=self.source_drain_pos[0] + 0.5*self.m2_width - bl_x)
        offset = vector(self.source_drain_pos[2] - 0.5*self.m2_width, bottom_connection_y-self.m2_width)
        self.add_rect("metal2",offset=offset, width=br_x-offset.x)

        self.add_layout_pin("bl", "metal2", offset=vector(bl_x, 0), height=bottom_connection_y)
        self.add_layout_pin("br", "metal2", offset=vector(br_x, 0), height=bottom_connection_y)



        
    def add_ptx_inst(self):
        """Adds both the upper_pmos and lower_pmos to the module"""

        self.pmos = ptx_spice(tx_type="pmos",
                              width=self.ptx_width, mults=1)
        self.add_inst(name="equalizer_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["bl", "en", "br", "vdd"])
        self.add_inst(name="bl_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["bl", "en", "vdd", "vdd"])
        self.add_inst(name="br_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["br", "en", "vdd", "vdd"])

    def drc_fill(self):
        fill_height = self.ptx_width
        fill_width = utils.ceil(self.minarea_metal1_contact/fill_height)
        if fill_width < self.m1_width:
            return
        offsets = [0.5*(self.m1_width-fill_width), 0, 0.5*(fill_width-self.m1_width)]
        fill_indices = [0, 2, 3]
        for i in range(3):
            x_offset = self.source_drain_pos[fill_indices[i]] + offsets[i]
            self.add_rect_center("metal1", offset=vector(x_offset, self.active_mid_y),
                                 width=fill_width, height=fill_height)


class precharge_tap(design.design):
    def __init__(self, precharge_cell: precharge):

        super().__init__("precharge_tap")

        self.height = precharge_cell.height
        self.precharge_cell = precharge_cell

        self.create_layout()

    def create_layout(self):
        body_tap = utils.get_body_tap()
        self.width = body_tap.width

        vdd_rail = utils.get_libcell_pins(["vdd"], OPTS.body_tap)["vdd"][0]

        precharge_vdd = self.precharge_cell.get_pin("vdd")
        self.add_rect("metal3", offset=vector(0, precharge_vdd.by()), width=self.width,
                      height=precharge_vdd.height())
        en_pin = self.precharge_cell.get_pin("en")

        max_via_height = precharge_vdd.uy() - en_pin.uy() - self.line_end_space
        num_vias = 1
        while True:
            sample_contact = contact.contact(m1m2.layer_stack, dimensions=[1, num_vias])
            if sample_contact.height > max_via_height:
                num_vias -= 1
                sample_contact = contact.contact(m1m2.layer_stack, dimensions=[1, num_vias])
                break
            num_vias += 1

        self.add_rect(vdd_rail.layer, offset=vector(vdd_rail.lx(), 0), width=vdd_rail.width(), height=self.height)
        via_offset = vector(vdd_rail.cx()-0.5*m1m2.second_layer_width,
                            precharge_vdd.uy()-sample_contact.second_layer_height)
        m1m2_cont = self.add_contact(m1m2.layer_stack, offset=via_offset, size=[1, num_vias])
        self.add_contact(m2m3.layer_stack, offset=via_offset, size=[1, num_vias])
        self.add_contact(m3m4.layer_stack, offset=via_offset, size=[1, num_vias])
        m2_area = m1m2_cont.width * m1m2.height
        if m2_area < self.minarea_metal1_contact:
            self.add_rect(METAL2, offset=vector(vdd_rail.lx(), via_offset.y), width=vdd_rail.width(),
                          height=m1m2_cont.height)


