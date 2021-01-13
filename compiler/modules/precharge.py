import debug
from base import contact
from base import design
from base import utils
from base.contact import m1m2, m2m3, m3m4
from base.design import METAL2, METAL1, METAL3
from base.vector import vector
from base.well_active_contacts import calculate_contact_width
from globals import OPTS
from pgates.ptx_spice import ptx_spice
from tech import drc, parameter, layer as tech_layers, add_tech_layers, info


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
        self.ptx_width = utils.round_to_grid(size * self.beta * parameter["min_tx_size"])
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
        add_tech_layers(self)
        self.add_ptx_inst()
        self.add_boundary()

    def set_layout_constants(self):

        self.mid_x = 0.5 * self.width

        # TODO should depend on bitcell width
        self.mults = 3

        self.well_contact_active_height = contact.well.first_layer_width
        self.well_contact_implant_height = max(self.implant_width,
                                               self.well_contact_active_height +
                                               2 * self.implant_enclose_active)

        # nwell contact top space requirement
        poly_to_well_cont_top = (self.poly_to_active + 0.5 * self.well_contact_active_height +
                                 0.5 * self.well_contact_implant_height)

        # space to add poly contacts
        active_to_poly_top = max(self.get_line_end_space(METAL1),
                                 self.get_line_end_space(METAL2))  # space to the en metal1
        active_to_poly_top += 0.5 * max(contact.poly.second_layer_width,
                                        m1m2.second_layer_width) # space to middle of poly contact
        self.active_to_poly_cont_mid = active_to_poly_top
        self.poly_top_space = active_to_poly_top = self.active_to_poly_cont_mid + 0.5 * contact.poly.first_layer_height

        # en pin top space requirement
        self.en_rail_height = self.bus_width
        # space based on M2 enable pin
        self.active_to_enable_top = self.get_line_end_space(METAL2) + self.en_rail_height
        en_rail_top_space = (self.active_to_enable_top + self.get_parallel_space(METAL2) +
                             m2m3.height)

        # space based on enable M1 contact to power rail
        min_rail_height = self.rail_height
        en_to_vdd_top_space = active_to_poly_top + self.parallel_line_space + min_rail_height

        self.top_space = max(active_to_poly_top + poly_to_well_cont_top, en_rail_top_space,
                             en_to_vdd_top_space)

        poly_enclosure = self.implant_enclose_poly

        self.bottom_space = poly_enclosure + self.poly_extend_active
        # ensure enough space for bitlines
        min_bitline_height = 2 * self.m2_width
        self.bottom_space = max(self.bottom_space, min_bitline_height)

        self.poly_height = (self.poly_extend_active + self.poly_top_space + self.ptx_width)
        self.poly_y_offset = max(poly_enclosure, self.bottom_space - self.poly_extend_active)

        self.height = self.bottom_space + self.ptx_width + self.top_space

        active_enclose_contact = max(drc["active_enclosure_contact"],
                                     (self.active_width - self.contact_width) / 2)
        self.poly_pitch = self.poly_width + self.poly_space
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate

        self.active_width = 2 * self.end_to_poly + self.mults * self.poly_pitch - self.poly_space

        active_space = drc.get("active_to_body_active", drc.get("active_to_active"))

        self.ptx_active_width = self.active_width  # for actual active
        if self.width - self.active_width < active_space:
            self.active_width = self.width + 2 * 0.5 * contact.well.first_layer_width

        self.active_bot_y = self.bottom_space
        self.active_mid_y = self.active_bot_y + 0.5 * self.ptx_width
        self.active_top = self.active_bot_y + self.ptx_width

        self.poly_contact_mid_y = self.active_top + self.active_to_poly_cont_mid

        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        self.contact_space = self.contact_pitch - self.contact_width

        self.implant_height = self.height - self.well_contact_implant_height

        self.implant_width = max(self.width, self.active_width + 2 * self.implant_enclose_ptx_active)

        self.calculate_body_contacts()
        self.nwell_height = (self.contact_y + 0.5 * self.well_contact_active_height +
                             self.well_enclose_active)
        self.nwell_width = max(self.implant_width,
                               max(self.active_width, self.well_contact_active_width) +
                               2 * self.well_enclose_ptx_active)

    def create_ptx(self):
        """Initializes all the pmos"""

        # add active
        self.active_rect = self.add_rect_center("active", offset=vector(self.mid_x, self.active_mid_y),
                                                width=self.active_width, height=self.ptx_width)

        poly_x_start = self.mid_x - 0.5 * self.ptx_active_width + self.end_to_poly
        # add poly
        # poly dummys
        if "po_dummy" in tech_layers:
            self.dummy_height = max(drc["po_dummy_min_height"], self.poly_height)
            poly_layers = 2 * ["po_dummy"] + ["poly"] * self.mults + 2 * ["po_dummy"]
            poly_x_start -= 2 * self.poly_pitch
            poly_heights = 2 * [self.dummy_height] + [self.poly_height] * self.mults + 2 * [self.dummy_height]
        else:
            poly_layers = ["poly"] * self.mults
            poly_heights = [self.poly_height] * self.mults

        for i in range(len(poly_layers)):
            offset = vector(poly_x_start + i * self.poly_pitch, self.poly_y_offset)
            self.add_rect(poly_layers[i], offset=offset, height=poly_heights[i], width=self.poly_width)

        # add implant
        self.add_rect_center("pimplant", offset=vector(self.mid_x, 0.5 * self.implant_height),
                             width=self.implant_width, height=self.implant_height)

        # add nwell
        x_offset = - 0.5 * (self.nwell_width - self.width)
        self.add_rect("nwell", offset=vector(x_offset, 0), width=self.nwell_width,
                      height=self.nwell_height)

    def connect_input_gates(self):
        # adjust contact positions such that there will be space for m1 to vdd
        left_contact_mid = max(self.mid_x - self.poly_pitch,
                               0.5 * self.m1_width + self.line_end_space +
                               0.5*contact.poly.second_layer_height)
        right_contact_mid = min(self.mid_x + self.poly_pitch,
                                self.width - 0.5 * self.m1_width - self.line_end_space -
                                0.5*contact.poly.second_layer_height)

        gate_pos = [left_contact_mid, self.mid_x, right_contact_mid]

        for x_offset in gate_pos:
            if info["horizontal_poly"]:
                self.add_contact_center(contact.poly.layer_stack,
                                        offset=vector(x_offset, self.poly_contact_mid_y),
                                        rotate=90)
            else:
                self.add_rect_center("contact", offset=vector(x_offset, self.poly_contact_mid_y))

        offset = vector(self.mid_x, self.poly_contact_mid_y)

        via_y = max(offset.y, self.active_rect.uy() + self.get_parallel_space(METAL2) +
                    0.5 * m1m2.second_layer_width)

        self.add_contact_center(m1m2.layer_stack, offset=vector(offset.x, via_y), rotate=90)

        m1_poly_extension = 0.5 * contact.poly.second_layer_height
        en_m1_width = 2 * m1_poly_extension + gate_pos[2] - gate_pos[0]
        self.en_m1_rect = self.add_rect_center(METAL1, offset=offset, width=en_m1_width)

        y_offset = self.active_rect.uy() + self.get_line_end_space(METAL2)
        self.add_layout_pin("en", "metal2", offset=vector(0, y_offset),
                            width=self.width, height=self.en_rail_height)

    def calculate_body_contacts(self):

        active_width, body_contact = calculate_contact_width(self, self.width,
                                                             self.well_contact_active_height)
        self.implant_width = max(self.implant_width, active_width + 2 * self.implant_enclose_active)
        self.body_contact = body_contact
        self.well_contact_active_width = active_width

        self.contact_y = self.height - 0.5 * self.well_contact_implant_height

    def add_nwell_contacts(self):
        self.add_rect_center("nimplant", offset=vector(self.mid_x, self.contact_y),
                             width=self.implant_width,
                             height=self.well_contact_implant_height)

        m1_enable_pin_top = self.poly_contact_mid_y + 0.5 * self.m1_width
        vdd_space = self.get_parallel_space(METAL1)

        vdd_pin_y = m1_enable_pin_top + vdd_space
        pin_height = self.height - vdd_pin_y
        # cover via totally with appropriate m1 but match m1 and m3 pins
        self.add_rect(METAL1, offset=vector(0, vdd_pin_y),
                      width=self.width, height=pin_height)

        # m3 pin
        m3_vdd_y = self.active_top + self.active_to_enable_top + self.get_parallel_space(METAL2)
        for layer in [METAL1, METAL3]:
            vdd_pin = self.add_layout_pin("vdd", layer, offset=vector(0, m3_vdd_y),
                                          width=self.width, height=self.height - m3_vdd_y)
        self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_x, vdd_pin.cy()),
                                size=[1, 3], rotate=90)
        self.add_contact_center(m2m3.layer_stack, offset=vector(self.mid_x, vdd_pin.cy()),
                                size=[1, 3], rotate=90)

        self.add_rect_center("active", offset=vector(self.mid_x, self.contact_y),
                             width=self.well_contact_active_width,
                             height=self.well_contact_active_height)

        self.add_contact_center(self.body_contact.layer_stack, rotate=90,
                                offset=vector(self.mid_x, self.contact_y),
                                size=self.body_contact.dimensions)

    def add_active_contacts(self):
        no_contacts = self.calculate_num_contacts(self.ptx_width)
        m1m2_contacts = max(1, no_contacts - 1)

        self.source_drain_pos = []

        self.active_contact = None

        extension = 0.5 * contact.well.first_layer_width
        mid_to_contact = 0.5 * self.poly_pitch

        x_offsets = [self.active_rect.lx() + extension,
                     self.mid_x - mid_to_contact,
                     self.mid_x + mid_to_contact,
                     self.active_rect.rx() - extension]

        for i in range(4):
            offset = vector(x_offsets[i], self.active_mid_y)
            self.source_drain_pos.append(offset.x)
            self.active_contact = self.add_contact_center(layers=contact.contact.active_layers,
                                                          size=[1, no_contacts], offset=offset)

            if i in [0, 3]:
                if i == 0:
                    target_x = min(0, self.en_m1_rect.lx() - self.line_end_space - self.m1_width)
                else:
                    target_x = max(self.width - self.m1_width,
                                   self.en_m1_rect.rx() + self.line_end_space)
                self.add_rect(METAL1, offset=offset - vector(0.5 * self.m1_width, 0),
                              height=self.active_top - offset.y)
                y_offset = self.active_top - self.m1_width
                self.add_rect(METAL1, offset=vector(target_x, y_offset),
                              width=offset.x - target_x)
                self.add_rect(METAL1, offset=vector(target_x, y_offset),
                              height=self.contact_y - y_offset)
            else:
                self.add_contact_center(layers=contact.contact.m1m2_layers,
                                        size=[1, m1m2_contacts], offset=offset)

    def connect_bitlines(self):

        bl_x = self.bitcell.get_pin("BL").lx()
        br_x = self.bitcell.get_pin("BR").lx()

        bottom_connection_y = self.active_bot_y - self.line_end_space

        for i in [1, 2]:
            x_offset = self.source_drain_pos[i] - 0.5 * self.m2_width
            self.add_rect("metal2", offset=vector(x_offset, bottom_connection_y),
                          height=self.active_mid_y - bottom_connection_y)

        offset = vector(bl_x, bottom_connection_y - self.m2_width)
        self.add_rect("metal2", offset=offset, width=self.source_drain_pos[1] + 0.5 * self.m2_width - bl_x)
        offset = vector(self.source_drain_pos[2] - 0.5 * self.m2_width, bottom_connection_y - self.m2_width)
        self.add_rect("metal2", offset=offset, width=br_x - offset.x)

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

        min_area = self.get_min_area(METAL1)
        min_height = min_area / self.m1_width
        if self.active_contact.height > min_height:
            return

        fill_width = self.poly_pitch - self.get_parallel_space(METAL1)
        fill_height = utils.ceil(min_area / fill_width)
        fill_height = max(fill_height, 0.5 * self.ptx_width + 0.5 * self.active_contact.height)
        fill_width = max(self.active_contact.width, utils.ceil(min_area / fill_height))

        fill_indices = [1, 2]
        for i in range(2):
            x_offset = self.source_drain_pos[fill_indices[i]] - 0.5 * fill_width
            y_offset = self.active_top - fill_height
            self.add_rect("metal1", offset=vector(x_offset, y_offset),
                          width=fill_width, height=fill_height)

    def is_delay_primitive(self):
        return True

    def get_driver_resistance(self, pin_name, use_max_res=False, interpolate=None, corner=None):
        return self.pmos.get_driver_resistance("d", use_max_res, interpolate=True, corner=corner)


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

        precharge_vdd = next(x for x in self.precharge_cell.get_pins("vdd") if x.layer == METAL3)
        self.add_rect(METAL3, offset=vector(0, precharge_vdd.by()), width=self.width,
                      height=precharge_vdd.height())
        en_pin = self.precharge_cell.get_pin("en")

        max_via_height = precharge_vdd.uy() - en_pin.uy() - self.get_parallel_space(METAL2)
        num_vias = 1
        while True:
            sample_contact = contact.contact(m1m2.layer_stack, dimensions=[1, num_vias])
            if sample_contact.height > max_via_height:
                num_vias -= 1
                sample_contact = contact.contact(m1m2.layer_stack, dimensions=[1, num_vias])
                break
            num_vias += 1

        self.add_rect(vdd_rail.layer, offset=vector(vdd_rail.lx(), 0), width=vdd_rail.width(),
                      height=self.height)
        via_offset = vector(vdd_rail.cx() - 0.5 * m1m2.second_layer_width,
                            precharge_vdd.uy() - sample_contact.second_layer_height)
        m1m2_cont = self.add_contact(m1m2.layer_stack, offset=via_offset, size=[1, num_vias])
        self.add_contact(m2m3.layer_stack, offset=via_offset, size=[1, num_vias])
        self.add_contact(m3m4.layer_stack, offset=via_offset, size=[1, num_vias])
        fill_height, fill_width = self.calculate_min_area_fill(m1m2_cont.height, layer=METAL2)
        self.add_rect(METAL2, offset=vector(vdd_rail.cx() - 0.5 * fill_width, via_offset.y),
                      width=fill_width, height=fill_height)
