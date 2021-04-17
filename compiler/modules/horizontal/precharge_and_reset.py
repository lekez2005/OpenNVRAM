import math

import debug
from base import contact
from base.contact import m1m2, m2m3, cross_m2m3, cross_m3m4, cross_m1m2
from base.design import design, METAL1, METAL3, METAL2, PIMP, NIMP, ACTIVE, PWELL, NWELL, POLY
from base.hierarchy_layout import GDS_ROT_90, GDS_ROT_270
from base.vector import vector
from base.well_active_contacts import calculate_contact_width
from globals import OPTS
from pgates.ptx import ptx
from tech import drc, parameter


class PrechargeAndReset(design):
    """Precharge bl and reset br"""

    def __init__(self, name, size=1, beta=None, mirror=False):
        design.__init__(self, name)
        debug.info(2, "create single precharge_reset cell: {0}".format(name))
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)

        if beta is None:
            beta = parameter["beta"]
        self.beta = beta
        self.size = size
        self.mirror = mirror

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        self.add_pin_list(["bl", "br", "en", "br_reset", "vdd", "gnd"])

    def create_layout(self):
        self.calculate_constraints()
        self.add_tx()
        self.add_layout_pins()
        self.add_enable_pins()
        self.connect_bitlines()
        self.connect_power_pins()
        self.add_body_contacts()
        self.add_boundary()

    def create_transistors(self):
        right_space = max(0.5 * self.active_space,
                          self.get_line_end_space(METAL1) + 0.5 * self.m1_width)

        left_space = (0.5 * contact.poly.second_layer_height +
                      self.get_line_end_space(METAL1))

        if contact.poly.first_layer_width > contact.poly.contact_width:
            left_space = max(left_space,
                             0.5 * contact.poly.first_layer_height + self.poly_to_active)

        self.ptx_active_x = left_space

        available_width = self.bitcell.width - (left_space + right_space)

        all_tx = []
        for scale_factor, tx_type in zip([1, self.beta], ["nmos", "pmos"]):
            tx_width = scale_factor * self.size * self.min_tx_width
            num_fingers = math.ceil(tx_width / available_width)
            finger_width = max(self.min_tx_width, tx_width / num_fingers)
            tx = ptx(width=finger_width, mults=num_fingers, tx_type=tx_type, dummy_pos=[0, 1, 2])
            self.add_mod(tx)
            all_tx.append(tx)

        self.nmos, self.pmos = all_tx

    def calculate_constraints(self):
        self.active_space = drc.get("active_to_body_active", drc.get("active_to_active"))
        self.width = self.bitcell.width

        self.create_transistors()

        self.contact_pitch = contact.active.contact_pitch
        self.contact_active_height = contact_active_height = contact.well.first_layer_width
        self.contact_active_width, self.body_contact = calculate_contact_width(self, self.bitcell.width,
                                                                               contact_active_height)

        # calculate tx y offset
        # based on active distance
        tx_active_space = 0.5 * contact_active_height + self.active_space
        # based on implants
        tx_implant_space = (max(0.5 * self.implant_width,
                                0.5 * contact_active_height + self.implant_enclose_active) +
                            self.implant_enclose_ptx_active)
        # based on poly, active
        tx_poly_active_space = 0.5 * contact_active_height + self.poly_extend_active + self.poly_to_active
        # based on power pin
        tx_gnd_space = 0.5 * self.rail_height + self.get_parallel_space(METAL1)

        self.nmos_y_offset = max(tx_active_space, tx_implant_space, tx_poly_active_space,
                                 tx_gnd_space)

        middle_space = max(self.active_space, 2 * self.well_enclose_ptx_active)
        self.pmos_y_offset = self.nmos_y_offset + self.nmos.active_width + middle_space

        self.mid_y = self.pmos_y_offset - 0.5 * middle_space
        self.height = self.pmos_y_offset + self.pmos.active_width + self.nmos_y_offset

    def add_tx(self):
        nmos_gate_mid_y = self.nmos.get_pins("G")[0].cy()
        nmos_active_x = self.nmos.height - (self.nmos.height - nmos_gate_mid_y)
        self.nmos_inst = self.add_inst("br_nmos", self.nmos, offset=vector(nmos_active_x,
                                                                           self.nmos_y_offset),
                                       rotate=GDS_ROT_90)
        self.connect_inst(["br", "br_reset", "gnd", "gnd"])

        pmos_gate_mid_y = self.pmos.get_pins("G")[0].cy()
        self.pmos_inst = self.add_inst("bl_pmos", self.pmos,
                                       offset=vector(-pmos_gate_mid_y,
                                                     self.pmos_y_offset + self.pmos.width),
                                       rotate=GDS_ROT_270)
        self.connect_inst(["bl", "en", "vdd", "vdd"])

    def add_layout_pins(self):
        y_offsets = [self.height, 0]
        for i, pin_name in enumerate(["vdd", "gnd"]):
            for layer in [METAL1, METAL3]:
                self.add_layout_pin_center_rect(pin_name, layer,
                                                offset=vector(0.5 * self.width, y_offsets[i]),
                                                width=self.width + self.m1_width, height=self.rail_height)

    def add_enable_pins(self):
        all_tx = [self.nmos_inst, self.pmos_inst]
        pin_names = ["br_reset", "en"]
        for tx, pin_name in zip(all_tx, pin_names):
            gate_pins = tx.get_pins("G")
            top_pin = max(gate_pins, key=lambda x: x.uy())
            bottom_pin = min(gate_pins, key=lambda x: x.by())
            mid_y = 0.5 * (bottom_pin.cy() + top_pin.cy())
            self.add_rect(METAL1, offset=vector(-0.5 * contact.poly.second_layer_height, bottom_pin.cy()),
                          height=top_pin.cy() - bottom_pin.cy(),
                          width=contact.poly.second_layer_height)
            self.add_cross_contact_center(cross_m1m2, vector(0, mid_y), rotate=True)
            self.add_cross_contact_center(cross_m2m3, vector(0, mid_y), rotate=False)

            self.add_layout_pin(pin_name, METAL3, vector(-0.5 * m2m3.height, mid_y - 0.5 * self.bus_width),
                                width=self.width + 0.5 * m2m3.height, height=self.bus_width)

            for poly_rect in tx.mod.get_layer_shapes(POLY):
                width = poly_rect.height - 0.5 * contact.poly.first_layer_height
                if (self.width - width) < 0.5 * self.poly_vert_space:
                    poly_y = tx.by() + poly_rect.lx()
                    self.add_rect(POLY, offset=vector(width, poly_y), width=self.width - width,
                                  height=poly_rect.width)

    def connect_bitlines(self):
        all_tx = [self.nmos_inst, self.pmos_inst]
        pin_names = ["br", "bl"]

        for tx, pin_name in zip(all_tx, pin_names):
            bitcell_pin = self.bitcell.get_pin(pin_name)

            if self.mirror:
                pin = self.add_layout_pin(pin_name, bitcell_pin.layer,
                                          vector(self.width - bitcell_pin.rx(), 0),
                                          width=bitcell_pin.width(),
                                          height=self.height)
            else:
                pin = self.add_layout_pin(pin_name, bitcell_pin.layer,
                                          vector(bitcell_pin.lx(), 0), width=bitcell_pin.width(),
                                          height=self.height)

            if pin.lx() > 0.5 * self.width:
                via_x = 0.5 * self.width + m1m2.height
                m2_x = max(via_x, pin.cx() - 0.5 * self.m2_width)
            else:
                via_x = 0.5 * self.width
                m2_x = max(pin.cx() - 0.5 * self.m2_width,
                           0.5 * m2m3.width + self.get_line_end_space(METAL2))
            for drain_pin in tx.get_pins("D"):
                self.add_rect(METAL1, offset=vector(via_x, drain_pin.by()), width=drain_pin.cx() - via_x,
                              height=drain_pin.height())
                via_y = drain_pin.cy() - 0.5 * m1m2.width
                self.add_contact(m1m2.layer_stack,
                                 offset=vector(via_x, via_y), rotate=90)
                self.add_rect(METAL2, offset=vector(via_x, via_y), width=m2_x - via_x,
                              height=m1m2.second_layer_width)

                if via_y > self.mid_y:
                    height = via_y - self.mid_y + self.m2_width
                else:
                    height = via_y - self.mid_y
                self.add_rect(METAL2, offset=vector(m2_x, self.mid_y), height=height)
                self.add_cross_contact_center(cross_m2m3, vector(m2_x + 0.5 * self.m2_width, self.mid_y))
                self.add_cross_contact_center(cross_m3m4, vector(bitcell_pin.cx(), self.mid_y),
                                              rotate=True)

    def connect_power_pins(self):
        all_tx = [self.nmos_inst, self.pmos_inst]
        power_pins = ["gnd", "vdd"]
        for tx, pin_name in zip(all_tx, power_pins):
            power_pin = self.get_pins(pin_name)[0]
            for source_pin in tx.get_pins("S"):
                self.add_rect(METAL1, offset=source_pin.lr(), width=self.width - source_pin.rx(),
                              height=source_pin.height())
                if source_pin.cy() > power_pin.cy():
                    y_offset = source_pin.uy()
                else:
                    y_offset = source_pin.by()
                self.add_rect(METAL1, offset=vector(self.width - 0.5 * self.m1_width, y_offset),
                              width=self.m1_width, height=power_pin.cy() - y_offset)
            mid_offset = vector(0.5 * self.width, power_pin.cy())
            for via in [m1m2, m2m3]:
                self.add_contact_center(via.layer_stack, offset=mid_offset, rotate=90)
            fill_height = m1m2.height
            _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)
            if fill_width > self.m2_width:
                self.add_rect_center(METAL2, mid_offset, width=fill_width, height=fill_height)

    def add_body_contacts(self):
        power_pins = ["gnd", "vdd"]
        implants = [PIMP, NIMP]
        for implant_layer, pin_name in zip(implants, power_pins):
            power_pin = self.get_pins(pin_name)[0]
            mid_offset = vector(0.5 * self.width, power_pin.cy())
            self.add_contact_center(contact.well.layer_stack, offset=mid_offset,
                                    size=self.body_contact.dimensions, rotate=90)
            self.add_rect_center(ACTIVE, offset=mid_offset, width=self.contact_active_width,
                                 height=self.contact_active_height)
            implant_width = max(self.width, self.contact_active_width + 2 * self.implant_enclose_active)
            self.add_rect_center(implant_layer, offset=mid_offset, width=implant_width,
                                 height=self.contact_active_height + 2 * self.implant_enclose_active)
            if implant_layer == PIMP:
                if not self.has_pwell:
                    continue
                top_y = self.mid_y
                bottom_y = - (0.5 * self.contact_active_height + self.well_enclose_active)
                well_layer = PWELL
            else:
                top_y = self.height + 0.5 * self.contact_active_height + self.well_enclose_active
                bottom_y = self.mid_y
                well_layer = NWELL

            well_x = min(-self.well_enclose_active,
                         -(0.5 * contact.poly.first_layer_height + self.implant_enclose_poly))
            self.add_rect(well_layer, offset=vector(well_x, bottom_y),
                          width=self.width + self.well_enclose_active - well_x,
                          height=top_y - bottom_y)

    def is_delay_primitive(self):
        return True

    def get_driver_resistance(self, pin_name, use_max_res=False, interpolate=None, corner=None):
        return self.pmos.get_driver_resistance("d", use_max_res, interpolate=True, corner=corner)
