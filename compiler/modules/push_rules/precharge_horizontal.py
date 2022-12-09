import math

import debug
from base import contact, utils
from base.analog_cell_mixin import AnalogMixin
from base.contact import m1m2, m2m3, poly_contact, cross_poly
from base.design import METAL1, PO_DUMMY, ACTIVE, POLY, PIMP, NIMP, NWELL, CONTACT, METAL2, METAL3
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from base.well_active_contacts import get_max_contact, calculate_num_contacts
from modules.precharge import precharge
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice
from tech import drc


class precharge_horizontal(precharge):
    rotation_for_drc = GDS_ROT_270

    def set_layout_constants(self):
        # assume there will be no space between polys
        left_space = 0.5 * poly_contact.w_2 + self.get_parallel_space(METAL1)
        self.left_space = left_space

        active_space = drc.get("active_to_body_active", self.get_space("active"))

        right_space = max(0.5 * active_space,
                          self.get_parallel_space(METAL1) + 0.5 * self.bus_width)

        max_finger_width = self.width - (left_space + right_space)
        num_fingers = math.ceil(self.ptx_width / max_finger_width)
        finger_width = max(self.min_tx_width, self.ptx_width / num_fingers)

        self.driver_num_fingers = num_fingers
        total_fingers = 1 + 2 * num_fingers
        tx_mod = self.tx_mod = ptx(width=finger_width, mults=total_fingers, tx_type="pmos")
        self.add_mod(tx_mod)

        # debug.pycharm_debug()
        if self.has_dummy:
            tx_y_offset = - tx_mod.get_max_shape(PO_DUMMY, "lx").cx()
            dummy_top = tx_mod.get_max_shape(PO_DUMMY, "rx").rx() + tx_y_offset
            self.contact_active_y = dummy_top + drc["poly_dummy_to_active"]
            self.implant_top = self.contact_active_y - self.implant_enclose_active
            self.implant_top = max(self.implant_top,
                                   tx_y_offset + tx_mod.get_max_shape(PIMP, "rx").rx())
            self.contact_active_y = max(self.contact_active_y, self.implant_top + self.implant_enclose_active)

        else:
            tx_y_offset = self.bus_width
            self.implant_top = tx_y_offset + tx_mod.get_max_shape(PIMP, "rx").rx()
        self.tx_y_offset = tx_y_offset

        # Calculate well contacts offsets
        self.contact_implant_top = self.implant_top + self.implant_width
        self.contact_active_top = max(contact.well.first_layer_height + self.contact_active_y,
                                      self.contact_implant_top - self.implant_enclose_active)
        self.contact_implant_top = max(self.contact_implant_top, self.contact_active_top
                                       + self.implant_enclose_active)
        self.height = self.contact_implant_top

    def create_ptx(self):
        active_rect = self.tx_mod.get_max_shape(ACTIVE, "by")
        x_offset = self.left_space - active_rect.by() + self.tx_mod.height
        offset = vector(x_offset, self.tx_y_offset)
        debug.info(0, "precharge cell offsets: %.5g, %.5g", offset.x, offset.y)
        # debug.pycharm_debug()
        self.tx_inst = self.add_inst(name="tx", mod=self.tx_mod, offset=offset, rotate=90)
        self.connect_inst([], check=False)

    def add_ptx_inst(self):
        """Adds both the upper_pmos and lower_pmos to the module"""

        equalizer = ptx_spice(tx_type="pmos", width=self.tx_mod.tx_width, mults=1)
        self.add_inst(name="equalizer_pmos", mod=equalizer, offset=vector(0, 0))
        self.connect_inst(["bl", "en", "br", "vdd"])

        self.pmos = ptx_spice(tx_type="pmos", width=self.tx_mod.tx_width,
                              mults=self.driver_num_fingers)
        self.add_inst(name="bl_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["bl", "en", "vdd", "vdd"])
        self.add_inst(name="br_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["br", "en", "vdd", "vdd"])

    def connect_input_gates(self):
        # add en pin
        pin_height = self.bus_width
        pin_x = - 0.5 * m2m3.second_layer_width
        self.add_layout_pin("en", METAL3, offset=vector(pin_x, 0),
                            width=self.width - pin_x, height=pin_height)
        # add vias to M3 and fill m2
        bl_pin = self.bitcell.get_pin("bl")
        fill_width = min(m2m3.height, 2 * (bl_pin.lx() - self.get_parallel_space(METAL2)))
        _, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL2)
        if fill_height:
            self.add_rect(METAL2, offset=vector(-0.5 * fill_width, 0), width=fill_width,
                          height=fill_height)
        via_offset = vector(0, 0.5 * m2m3.height)
        for via in [m1m2, m2m3]:
            self.add_contact_center(via.layer_stack, offset=via_offset)

        gate_pins = list(sorted(self.tx_inst.get_pins("G"), key=lambda x: x.by()))
        threshold = utils.round_to_grid(self.width - 0.5 * self.poly_vert_space)
        extend_poly = utils.round_to_grid(gate_pins[0].rx()) > threshold

        for pin in gate_pins:
            self.add_cross_contact_center(cross_poly, vector(0, pin.cy()), rotate=True)
            if extend_poly:
                self.add_rect(POLY, pin.lr(), width=self.width - pin.rx(), height=pin.height())

        self.add_rect(METAL1, vector(-0.5 * poly_contact.w_2, 0), height=gate_pins[-1].cy(),
                      width=poly_contact.w_2)

    def add_nwell_contacts(self):
        implant_x = - (0.5 * poly_contact.h_1 + self.implant_enclose_poly)
        implant_right = self.width + self.implant_enclose_poly

        # add implants
        layers = [PIMP, NIMP]

        pimp_y = self.tx_inst.get_max_shape(PIMP, "by").by()
        pimp_top = self.tx_inst.get_max_shape(PIMP, "uy").uy()
        nimp_y = pimp_top
        nimp_top = self.contact_implant_top

        y_offsets = [[pimp_y, pimp_top], [nimp_y, nimp_top]]

        for i in range(2):
            self.add_rect(layers[i], offset=vector(implant_x, y_offsets[i][0]),
                          width=implant_right - implant_x,
                          height=y_offsets[i][1] - y_offsets[i][0])

        # Add Nwell
        nwell_top = self.contact_implant_top + self.well_enclose_active
        nwell_left = min(- self.well_enclose_active, implant_x)
        nwell_right = max(self.width + self.well_enclose_active, implant_right)
        self.add_rect(NWELL, offset=vector(nwell_left, 0), height=nwell_top,
                      width=nwell_right - nwell_left)

        # add the contacts

        num_contacts = calculate_num_contacts(self, self.width - self.contact_spacing,
                                              layer_stack=contact.well.layer_stack,
                                              return_sample=False)
        active_rect = self.add_rect(ACTIVE, offset=vector(0, self.contact_active_y),
                                    width=self.width,
                                    height=self.contact_active_top - self.contact_active_y)
        contact_pitch = self.contact_width + self.contact_spacing
        total_contact = (contact_pitch * (num_contacts - 1)
                         + self.contact_width)
        x_offset = 0.5 * self.width - 0.5 * total_contact
        y_offset = active_rect.cy() - 0.5 * self.contact_width
        for i in range(num_contacts):
            self.add_rect(CONTACT, offset=vector(x_offset, y_offset))
            x_offset += contact_pitch

        pin_height = max(self.rail_height, 2 * (self.height - active_rect.cy()))
        pin_top = min(self.height, active_rect.cy() + 0.5 * pin_height)
        self.add_layout_pin("vdd", METAL1, offset=vector(-0.5 * self.m1_width, pin_top - pin_height),
                            width=self.width + self.m1_width, height=pin_height)

    def get_sorted_tx_pins(self):
        pins = list(sorted(self.tx_inst.get_pins("S") + self.tx_inst.get_pins("D"),
                           key=lambda x: x.by()))
        split_index = int(len(pins) / 2)
        return pins[:split_index], pins[split_index:]

    def get_vdd_tx_pins(self):
        bot_pins, top_pins = self.get_sorted_tx_pins()
        return list(sorted(bot_pins[-2::-2] + top_pins[1::2], key=lambda x: x.by()))

    def get_bitline_tx_pins(self):
        bot_pins, top_pins = self.get_sorted_tx_pins()

        return bot_pins[-1::-2], top_pins[0::2]

    def add_active_contacts(self):

        sample_pin = self.tx_inst.get_pins("S")[0]

        # calculate fill
        max_fill_height = self.tx_mod.poly_pitch - self.get_parallel_space(METAL1)
        _, fill_height = self.calculate_min_area_fill(sample_pin.width(), layer=METAL1)
        if utils.round_to_grid(fill_height) > max_fill_height:
            fill_height = max_fill_height
            _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL1)
        elif utils.round_to_grid(fill_height) <= utils.round_to_grid(sample_pin.height()):
            fill_width = 0
        else:
            fill_width = sample_pin.width()

        if fill_width > 0:
            self.metal_fill_height = fill_height
            bitline_pins = self.get_bitline_tx_pins()
            for bitline_pin in bitline_pins[0] + bitline_pins[1]:
                self.add_rect(METAL1, vector(bitline_pin.lx(),
                                             bitline_pin.cy() - 0.5 * fill_height),
                              width=fill_width, height=fill_height)
        else:
            self.metal_fill_height = None

        # create vdd rail
        min_vdd_rail_x = (max(sample_pin.lx() + fill_width, sample_pin.rx()) +
                          self.get_line_end_space(METAL1))
        vdd_rail_x = max(min_vdd_rail_x, self.width - 0.5 * self.rail_height)
        vdd_rail_width = 2 * (self.width - vdd_rail_x)

        vdd_pins = self.get_vdd_tx_pins()
        rail_y = vdd_pins[0].by()

        self.add_rect(METAL1, offset=vector(vdd_rail_x, rail_y), height=self.height - rail_y,
                      width=vdd_rail_width)
        # connect vdd pins to rail
        for vdd_pin in vdd_pins:
            self.add_rect(METAL1, vdd_pin.lr(), width=vdd_rail_x - vdd_pin.rx(),
                          height=vdd_pin.height())

    def connect_bitlines(self):
        active_rect = self.tx_inst.get_max_shape(ACTIVE, "lx")
        pin_names = ["BL", "BR"]
        adjacent_names = ["BR", "BL"]

        bitline_tx_pins = self.get_bitline_tx_pins()

        for i in range(2):
            bitcell_pin = self.bitcell.get_pin(pin_names[i])
            adjacent_pin = self.bitcell.get_pin(adjacent_names[i])
            if i == 0:
                max_x = adjacent_pin.lx() - self.get_line_end_space(METAL2)
                min_x = active_rect.lx()
            else:
                min_x = adjacent_pin.rx() + self.get_line_end_space(METAL2)
                max_x = active_rect.rx()

            cont = get_max_contact(m1m2.layer_stack, max_x - min_x)
            if i == 0:
                cont_x = max_x - 0.5 * cont.h_2
            else:
                cont_x = min_x + 0.5 * cont.h_2

            for tx_pin in bitline_tx_pins[i]:
                cont_inst = self.add_contact_center(m1m2.layer_stack, vector(cont_x, tx_pin.cy()),
                                                    rotate=90, size=cont.dimensions)
                self.add_rect(METAL2, vector(bitcell_pin.lx(), tx_pin.cy() - 0.5 * cont.w_2),
                              width=cont_x - bitcell_pin.lx())

                if self.metal_fill_height:
                    fill_x = utils.floor(cont_inst.lx())
                    fill_right = utils.ceil(cont_inst.rx())
                    self.add_rect(METAL1, vector(fill_x, tx_pin.cy()
                                                 - 0.5 * self.metal_fill_height),
                                  height=self.metal_fill_height,
                                  width=fill_right - fill_x)

            self.add_layout_pin(pin_names[i].lower(), METAL2, offset=vector(bitcell_pin.lx(), 0),
                                width=bitcell_pin.width(), height=self.height)

    def drc_fill(self):
        vdd_pin = self.get_pin("vdd")
        AnalogMixin.add_m1_m3_power_via(self, vdd_pin, recursive=False)
        for rect in self.tx_inst.get_layer_shapes(PO_DUMMY):
            self.add_rect(PO_DUMMY, vector(0, rect.by()), width=self.width,
                          height=rect.height)
