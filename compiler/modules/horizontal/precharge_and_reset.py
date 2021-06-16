import math

import debug
from base import contact
from base.contact import m1m2, m2m3, cross_m2m3, cross_m3m4, cross_m1m2
from base.design import design, METAL1, METAL3, METAL2, PIMP, NIMP, ACTIVE, PWELL, NWELL, POLY
from base.hierarchy_layout import GDS_ROT_90, GDS_ROT_270
from base.vector import vector
from base.well_active_contacts import calculate_contact_width
from globals import OPTS
from modules.precharge import precharge_characterization
from pgates.ptx import ptx
from tech import drc, parameter


class PrechargeAndReset(precharge_characterization, design):
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
        self.precharge_bl = getattr(OPTS, "precharge_bl", True)

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        enable_pin = ["en"] * self.precharge_bl
        self.add_pin_list(["bl", "br"] + enable_pin + ["bl_reset", "br_reset"])
        if self.precharge_bl:
            self.add_pin("vdd")
        self.add_pin("gnd")

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
        self.eq_nmos = ptx(width=self.nmos.tx_width, mults=1, tx_type="nmos",
                           dummy_pos=[])
        self.add_mod(self.eq_nmos)

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

        self.bl_y_offset = max(tx_active_space, tx_implant_space, tx_poly_active_space,
                               tx_gnd_space)

        middle_space = max(self.active_space, 2 * self.well_enclose_ptx_active)

        # align drain and source
        bl_drain_y = max(self.nmos.get_pins("D") + self.nmos.get_pins("S"),
                         key=lambda x: x.cx()).cx() + self.bl_y_offset
        eq_source = self.eq_nmos.get_pin("S")
        self.eq_y_offset = bl_drain_y - eq_source.cx()

        eq_drain_y = self.eq_y_offset + self.eq_nmos.get_pin("D").cx()

        br_source = min(self.nmos.get_pins("S") + self.nmos.get_pins("D"),
                        key=lambda x: x.cx())
        self.br_y_offset = eq_drain_y - br_source.cx()

        if self.precharge_bl:
            self.pmos_y_offset = self.br_y_offset + self.nmos.active_width + middle_space

            self.mid_y = self.pmos_y_offset - 0.5 * middle_space
            self.height = self.pmos_y_offset + self.pmos.active_width + self.bl_y_offset
        else:
            self.height = self.br_y_offset + self.nmos.active_width + 0.5 * middle_space

    def add_tx(self):
        nmos_gate_mid_y = self.nmos.get_pins("G")[0].cy()
        nmos_active_x = self.nmos.height - (self.nmos.height - nmos_gate_mid_y)

        self.nmos_br_inst = self.add_inst("br_nmos", self.nmos,
                                          offset=vector(nmos_active_x, self.br_y_offset),
                                          rotate=GDS_ROT_90)
        self.connect_inst(["br", "br_reset", "gnd", "gnd"])
        self.nmos_bl_inst = self.add_inst("bl_nmos", self.nmos,
                                          offset=vector(nmos_active_x, self.bl_y_offset),
                                          rotate=GDS_ROT_90)
        self.connect_inst(["bl", "bl_reset", "gnd", "gnd"])

        self.nmos_eq_inst = self.add_inst("eq_nmos", self.eq_nmos,
                                          offset=vector(nmos_active_x, self.eq_y_offset),
                                          rotate=GDS_ROT_90)
        self.connect_inst(["bl", "bl_reset", "br", "gnd"])

        if not self.precharge_bl:
            return
        pmos_gate_mid_y = self.pmos.get_pins("G")[0].cy()
        self.pmos_inst = self.add_inst("bl_pmos", self.pmos,
                                       offset=vector(-pmos_gate_mid_y,
                                                     self.pmos_y_offset + self.pmos.width),
                                       rotate=GDS_ROT_270)
        self.connect_inst(["bl", "en", "vdd", "vdd"])

    def add_layout_pins(self):
        power_pins = ["gnd", "vdd"] if self.precharge_bl else ["gnd"]
        y_offsets = [0, self.height]
        for i, pin_name in enumerate(power_pins):
            for layer in [METAL1, METAL3]:
                self.add_layout_pin_center_rect(pin_name, layer,
                                                offset=vector(0.5 * self.width, y_offsets[i]),
                                                width=self.width + self.m1_width, height=self.rail_height)

    def add_enable_pins(self):
        all_tx = ["nmos_bl_inst", "nmos_br_inst", "pmos_inst"]
        pin_names = ["bl_reset", "br_reset", "en"]
        for tx_name, pin_name in zip(all_tx, pin_names):
            tx = getattr(self, tx_name, None)
            if not tx:
                continue
            gate_pins = tx.get_pins("G")
            top_pin = max(gate_pins, key=lambda x: x.uy())
            bottom_pin = min(gate_pins, key=lambda x: x.by())
            mid_y = 0.5 * (bottom_pin.cy() + top_pin.cy())
            self.add_rect(METAL1, offset=vector(-0.5 * contact.poly.second_layer_height, bottom_pin.cy()),
                          height=top_pin.cy() - bottom_pin.cy(),
                          width=contact.poly.second_layer_height)
            self.add_cross_contact_center(cross_m1m2, vector(0, mid_y), rotate=True)
            self.add_cross_contact_center(cross_m2m3, vector(0, mid_y), rotate=False)

            self.add_layout_pin(pin_name, METAL3,
                                vector(-0.5 * m2m3.height, mid_y - 0.5 * self.bus_width),
                                width=self.width + 0.5 * m2m3.height, height=self.bus_width)

            for poly_rect in tx.mod.get_layer_shapes(POLY):
                width = poly_rect.height - 0.5 * contact.poly.first_layer_height
                if (self.width - width) < 0.5 * self.poly_vert_space:
                    poly_y = tx.by() + poly_rect.lx()
                    self.add_rect(POLY, offset=vector(width, poly_y), width=self.width - width,
                                  height=poly_rect.width)
        eq_gate = self.nmos_eq_inst.get_pin("G")
        bl_reset_pin = max(self.nmos_bl_inst.get_pins("G"), key=lambda x: x.uy())
        self.add_rect(bl_reset_pin.layer, offset=bl_reset_pin.ul(),
                      width=bl_reset_pin.width(),
                      height=eq_gate.by() - bl_reset_pin.uy())

    def connect_bitlines(self):

        if self.nmos.mults % 2 == 0:
            bl_pin = br_pin = "S"
        else:
            bl_pin = "D"
            br_pin = "S"

        def get_via_x(target_pin):
            if target_pin.lx() > 0.5 * self.width:
                via_x = 0.5 * self.width + m1m2.height
                m2_x = max(via_x, target_pin.cx() - 0.5 * self.m2_width)
            else:
                via_x = 0.5 * self.width
                m2_x = max(target_pin.cx() - 0.5 * self.m2_width,
                           0.5 * m2m3.width + self.get_line_end_space(METAL2))
            return via_x, m2_x

        def add_m2_via(tx_pin, via_x, m2_x):
            self.add_rect(METAL1, offset=vector(via_x, tx_pin.by()), width=tx_pin.cx() - via_x,
                          height=tx_pin.height())
            via_y = tx_pin.cy() - 0.5 * m1m2.width
            self.add_contact(m1m2.layer_stack,
                             offset=vector(via_x, via_y), rotate=90)
            self.add_rect(METAL2, offset=vector(via_x, via_y), width=m2_x - via_x,
                          height=m1m2.second_layer_width)
            return via_y

        def add_m4_via(m2_x, mid_y, height):
            self.add_rect(METAL2, offset=vector(m2_x, mid_y), height=height)
            self.add_cross_contact_center(cross_m2m3, vector(m2_x + 0.5 * self.m2_width, mid_y))
            self.add_cross_contact_center(cross_m3m4, vector(pin.cx(), mid_y),
                                          rotate=True)

        all_tx = [self.nmos_br_inst, self.nmos_bl_inst]
        pin_names = ["br", "bl"]
        tx_pins = [br_pin, bl_pin]
        y_offset = self.nmos_eq_inst.get_pin("G").cy()

        for tx, pin_name, tx_pin_name in zip(all_tx, pin_names, tx_pins):
            bitcell_pin = self.bitcell.get_pin(pin_name)

            if self.mirror:
                pin = self.add_layout_pin(pin_name, bitcell_pin.layer,
                                          vector(self.width - bitcell_pin.rx(), 0),
                                          width=bitcell_pin.width(),
                                          height=self.height)
            else:
                pin = self.add_layout_pin(pin_name, bitcell_pin.layer,
                                          vector(bitcell_pin.lx(), 0),
                                          width=bitcell_pin.width(),
                                          height=self.height)
            via_x_, m2_x_ = get_via_x(pin)

            for tx_pin in tx.get_pins(tx_pin_name):
                via_y_ = add_m2_via(tx_pin, via_x_, m2_x_)
                if via_y_ > y_offset:
                    height_ = via_y_ - y_offset + self.m2_width
                else:
                    height_ = via_y_ - y_offset
                add_m4_via(m2_x_, y_offset, height_)

        if not self.precharge_bl:
            return
        # bl precharge
        pin = self.get_pin("bl")
        via_x_, m2_x_ = get_via_x(pin)
        for tx_pin in self.pmos_inst.get_pins("S"):
            via_y_ = add_m2_via(tx_pin, via_x_, m2_x_)
            y_offset = self.mid_y
            height_ = via_y_ - y_offset + self.m2_width
            add_m4_via(m2_x_, y_offset, height_)

    def connect_power_pins(self):

        if self.nmos.mults % 2 == 0:
            bl_pin = br_pin = "D"
        else:
            bl_pin = "S"
            br_pin = "D"

        all_tx = ["nmos_bl_inst", "nmos_br_inst", "pmos_inst"]
        power_pins = ["gnd", "gnd", "vdd"]
        tx_pin_names = [bl_pin, br_pin, "D"]
        for tx_name, pin_name, tx_pin_name in zip(all_tx, power_pins, tx_pin_names):
            tx = getattr(self, tx_name, None)
            if not tx:
                continue
            power_pin = self.get_pins(pin_name)[0]
            for source_pin in tx.get_pins(tx_pin_name):
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
        if self.precharge_bl:
            power_pins = ["gnd", "vdd"]
        else:
            power_pins = ["gnd"]
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
                top_y = self.mid_y if self.precharge_bl else self.height
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
