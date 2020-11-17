import tech
from base import contact, utils
from base.contact import m1m2
from base.design import METAL1, PO_DUMMY, ACTIVE, POLY, PIMP, NIMP, NWELL, CONTACT, METAL2
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from base.well_implant_fills import calculate_tx_metal_fill
from modules.precharge import precharge
from modules.push_rules.push_bitcell_array import push_bitcell_array
from tech import drc, layer as tech_layers


class precharge_horizontal(precharge):
    rotation_for_drc = GDS_ROT_270

    def set_layout_constants(self):
        # Initially calculate offsets assuming max active will be used and there will be space between poly
        self.poly_x_offset = 0.5 * self.poly_to_field_poly
        poly_to_mid_contact = 0.5 * contact.poly.first_layer_height

        self.gate_contact_x = (self.poly_x_offset + poly_to_mid_contact
                               - 0.5 * self.contact_width)
        self.pin_right_x = self.gate_contact_x + 0.5 * self.contact_width + 0.5 * self.m1_width
        self.active_x = self.pin_right_x + self.get_line_end_space(METAL1)

        poly_to_active_x = self.active_x - self.poly_x_offset

        max_poly_right = self.width - self.poly_x_offset
        max_active_right = max_poly_right - self.poly_extend_active
        max_width = max_active_right - self.active_x

        if self.ptx_width > max_width:
            # re-calculate assuming no space between poly
            self.poly_x_offset = - poly_to_mid_contact
            self.active_x = self.poly_x_offset + poly_to_active_x
            max_active_right = self.width - 0.5 * self.poly_extend_active
            max_width = max_active_right - self.active_x
            has_poly_space = False
        else:
            has_poly_space = True

        assert max_width > self.ptx_width, "Maximum size supported is {:.3g}".format(
            max_width / self.min_tx_width / self.beta)

        # centralize active and recalculate poly and active offsets
        self.mid_x = 0.5 * self.width
        self.active_x = utils.round_to_grid(self.mid_x - 0.5 * self.ptx_width)
        self.active_right = self.active_x + self.ptx_width

        if has_poly_space:
            self.poly_x_offset = self.active_x - poly_to_active_x
            self.gate_contact_x = (self.poly_x_offset + poly_to_mid_contact
                                   - 0.5 * self.contact_width)
            self.poly_right_x = self.active_right + self.poly_extend_active
        else:
            self.poly_right_x = max(self.width, self.active_right + self.poly_extend_active)
            self.gate_contact_x = -0.5 * self.contact_width

        self.implant_x = min(0, self.poly_x_offset - self.implant_enclose_poly)
        self.implant_right = max(self.width, self.poly_right_x + self.implant_enclose_poly)

        # Calculate active y offsets
        active_to_poly = (drc["active_enclosure_contact"] + self.contact_width
                          + self.contact_to_gate)
        self.insert_poly_dummies = PO_DUMMY in tech_layers
        if self.insert_poly_dummies:
            self.dummy_y = -0.5 * self.poly_width
            self.poly_y = self.dummy_y + 2 * self.poly_pitch
            self.active_y = self.poly_y - active_to_poly
        else:
            self.active_y = 0.5 * self.get_wide_space(ACTIVE)
            self.poly_y = self.active_y + active_to_poly

        self.poly_top = self.poly_y + 2 * self.poly_pitch + self.poly_width
        self.active_top = self.poly_top + active_to_poly
        self.active_mid_y = 0.5 * (self.active_y + self.active_top)
        self.implant_bottom = min(0, self.active_y - self.implant_enclose_ptx_active)
        # Calculate well contacts offsets
        if self.insert_poly_dummies:
            self.dummy_top = self.poly_y + 4 * self.poly_pitch + self.poly_width
            self.contact_active_y = self.dummy_top + drc["poly_dummy_to_active"]
            self.implant_top = self.contact_active_y - self.implant_enclose_active
        else:
            self.implant_top = self.active_top + self.implant_enclose_ptx_active
            self.contact_active_y = self.implant_top + self.implant_enclose_active
        self.contact_implant_top = self.implant_top + self.implant_width
        self.contact_active_top = max(contact.well.first_layer_height,
                                      self.contact_implant_top - self.implant_enclose_active)
        self.contact_implant_top = max(self.contact_implant_top, self.contact_active_top
                                       + self.implant_enclose_active)
        self.height = self.contact_implant_top

    def create_ptx(self):
        # add active
        self.active_rect = self.add_rect(ACTIVE, offset=vector(self.active_x, self.active_y),
                                         width=self.ptx_width, height=self.active_top - self.active_y)
        # add poly
        poly_width = self.poly_right_x - self.poly_x_offset
        if self.insert_poly_dummies:
            layers = [PO_DUMMY, PO_DUMMY, POLY, POLY, POLY, PO_DUMMY, PO_DUMMY]
            y_offset = self.dummy_y
            poly_width = max(drc["po_dummy_min_height"], poly_width)
        else:
            layers = [POLY] * 3
            y_offset = self.poly_y
        for i in range(len(layers)):
            self.add_rect(layers[i], offset=vector(self.poly_x_offset,
                                                   y_offset + i * self.poly_pitch),
                          height=self.poly_width, width=poly_width)
        # add implants
        layers = [PIMP, NIMP]
        y_offsets = [[self.implant_bottom, self.implant_top],
                     [self.implant_top, self.contact_implant_top]]
        x_offsets = [[self.implant_x, self.implant_right],
                     [min(self.implant_x, -self.implant_enclose_active),
                      self.width + self.implant_enclose_active]]
        for i in range(2):
            self.add_rect(layers[i], offset=vector(x_offsets[i][0], y_offsets[i][0]),
                          width=x_offsets[i][1] - x_offsets[i][0],
                          height=y_offsets[i][1] - y_offsets[i][0])

        # Add Nwell
        nwell_top = self.contact_implant_top + self.well_enclose_active
        nwell_left = min(- self.well_enclose_active, self.implant_x)
        nwell_right = max(self.width + self.well_enclose_active, self.implant_right)
        self.add_rect(NWELL, offset=vector(nwell_left, 0), height=nwell_top,
                      width=nwell_right - nwell_left)

        if hasattr(tech, "add_tech_layers"):
            tech.add_tech_layers(self)

        self.add_boundary()

    def connect_input_gates(self):
        pin_height = push_bitcell_array.bitcell.get_pin("wl").height()
        pin_x = min(0, self.gate_contact_x + 0.5 * self.contact_width - 0.5 * m1m2.height)
        en_pin = self.add_layout_pin("en", METAL2, offset=vector(pin_x, 0),
                                     width=self.width - pin_x, height=pin_height)
        poly_contact_y = 0
        for i in range(3):
            poly_contact_y = (self.poly_y + i * self.poly_pitch + 0.5 * self.poly_width
                              - 0.5 * self.contact_width)
            self.add_rect(CONTACT, offset=vector(self.gate_contact_x, poly_contact_y))
        via_x = self.gate_contact_x + 0.5 * self.contact_width
        self.add_contact_center(m1m2.layer_stack, offset=vector(via_x, en_pin.cy()),
                                rotate=90)
        m1_extension = utils.round_to_grid(0.5 * (contact.poly.second_layer_height
                                                  - contact.poly.contact_width))
        y_top = poly_contact_y + self.contact_width + m1_extension
        self.add_rect(METAL1, offset=vector(via_x - 0.5 * self.m1_width, en_pin.cy()),
                      height=y_top - en_pin.cy())

    def add_nwell_contacts(self):
        num_contacts = self.calculate_num_contacts(self.width - self.contact_spacing)
        active_rect = self.add_rect(ACTIVE, offset=vector(0, self.contact_active_y),
                                    width=self.width,
                                    height=self.contact_active_top - self.contact_active_y)
        contact_pitch = self.contact_width + self.contact_spacing
        total_contact = (contact_pitch * (num_contacts - 1)
                         + self.contact_width)
        x_offset = self.mid_x - 0.5 * total_contact
        y_offset = active_rect.cy() - 0.5 * self.contact_width
        for i in range(num_contacts):
            self.add_rect(CONTACT, offset=vector(x_offset, y_offset))
            x_offset += contact_pitch

        pin_height = max(self.rail_height, 2 * (self.height - active_rect.cy()))
        pin_top = min(self.height, active_rect.cy() + 0.5 * pin_height)
        self.add_layout_pin("vdd", METAL1, offset=vector(-0.5 * self.m1_width, pin_top - pin_height),
                            width=self.width + self.m1_width, height=pin_height)

    def get_mid_contact_y(self, source_drain_index):
        """Get y offset of active contact for given source_drain_index"""
        base_y = self.poly_y - self.contact_to_gate - self.contact_width
        return base_y + source_drain_index * self.poly_pitch + 0.5 * self.contact_width

    def add_active_contacts(self):
        self.num_contacts = self.calculate_num_contacts(self.ptx_width)

        fill = calculate_tx_metal_fill(self.ptx_width, self)

        vdd_rail_x = self.width - 0.5 * self.m1_width

        for i in range(4):
            y_offset = self.get_mid_contact_y(i)
            contact_inst = self.add_contact_center(layers=contact.contact.active_layers,
                                                   size=[1, self.num_contacts],
                                                   offset=vector(self.active_rect.cx(), y_offset),
                                                   rotate=90)
            if i in [0, 3]:
                self.add_rect(METAL1, offset=vector(self.mid_x, y_offset - 0.5 * self.m1_width),
                              width=vdd_rail_x - self.mid_x)
            else:
                if contact_inst.height > self.get_drc_by_layer(METAL1, "minside_contact"):
                    continue

                adjacent_space = self.get_parallel_space(METAL1) + 0.5 * self.m1_width
                # adjacent drain contact will be min-width
                fill_below_contact = self.poly_pitch - adjacent_space
                # adjacent above contact will be another fill
                fill_above_contact = 0.5 * (self.poly_pitch - self.get_parallel_space(METAL1))

                fill_height = fill_above_contact + fill_below_contact
                fill_height, fill_width = self.calculate_min_m1_area(fill_height,
                                                                     min_height=contact_inst.width,
                                                                     layer=METAL1)
                if i == 1:
                    fill_y = y_offset - self.poly_pitch + adjacent_space
                else:
                    fill_y = y_offset + self.poly_pitch - adjacent_space - fill_height
                fill_x = max(self.active_rect.lx(), self.active_rect.cx() - 0.5 * fill_width)
                self.add_rect(METAL1, offset=vector(fill_x, fill_y),
                              width=fill_width, height=fill_height)

        rail_y = self.get_mid_contact_y(0) - 0.5 * self.m1_width
        self.add_rect(METAL1, offset=vector(vdd_rail_x, rail_y), height=self.height - rail_y)

    def connect_bitlines(self):
        drain_indices = [1, 2]
        pin_names = ["BL", "BR"]
        active_mid = self.active_rect.cx()
        for i in range(2):
            bitcell_pin = self.bitcell.get_pin(pin_names[i])
            y_offset = self.get_mid_contact_y(drain_indices[i])
            if i == 0:
                via_x = max(active_mid, self.active_rect.lx() + 0.5 * m1m2.height)
            else:
                via_x = active_mid + 0.5 * m1m2.height
            self.add_contact_center(m1m2.layer_stack, offset=vector(via_x, y_offset),
                                    rotate=90)
            self.add_rect(METAL2, offset=vector(bitcell_pin.lx(), y_offset - 0.5 * self.m2_width),
                          width=self.mid_x - bitcell_pin.lx())
            pin_y = y_offset - 0.5 * self.m2_width
            self.add_layout_pin(pin_names[i].lower(), METAL2, offset=vector(bitcell_pin.lx(), pin_y),
                                width=bitcell_pin.width(),
                                height=self.height - pin_y)

    def drc_fill(self):
        pass
