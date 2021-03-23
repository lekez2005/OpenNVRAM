from base import utils, contact
from base.contact import m1m2, m2m3
from base.design import METAL1, POLY, ACTIVE, PIMP, NIMP, NWELL, METAL3, CONTACT, METAL2
from base.vector import vector
from base.well_implant_fills import calculate_tx_metal_fill
from modules.horizontal.pinv_horizontal import pinv_horizontal
from modules.push_rules.push_bitcell_array import push_bitcell_array
from pgates.ptx_spice import ptx_spice
from tech import drc


class wordline_inverter(pinv_horizontal):
    @classmethod
    def get_name(cls, size=1, beta=None, mirror=False):
        beta, beta_suffix = cls.get_beta(beta, size)
        mirror_suffix = "_mirror" * mirror
        name = "wordline_inverter_{:.3g}{}{}".format(size, beta_suffix, mirror_suffix) \
            .replace(".", "__")
        return name

    def __init__(self, size=1, beta=None, mirror=False):
        self.mirror = mirror
        super().__init__(size, beta)

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "Z", "vdd", "gnd"])

    def add_ptx_insts(self):
        self.pmos = ptx_spice(self.pmos_finger_width, mults=self.num_fingers,
                              tx_type="pmos", tx_length=self.poly_width)
        self.add_inst(name="pinv_pmos",
                      mod=self.pmos,
                      offset=vector(0, 0))
        self.add_mod(self.pmos)
        self.connect_inst(["Z", "A", "vdd", "vdd"])
        self.nmos = ptx_spice(self.nmos_finger_width, mults=self.num_fingers,
                              tx_type="nmos", tx_length=self.poly_width)
        self.add_inst(name="pinv_nmos",
                      mod=self.nmos,
                      offset=vector(0, 0))
        self.add_mod(self.nmos)
        self.connect_inst(["Z", "A", "gnd", "gnd"])

    def calculate_fills(self, nmos_width, pmos_width):

        # TODO fix non-default pitch messes up fill calculations
        # Fix fill calculation to take min-width into account
        original_pitch = self.poly_pitch
        self.poly_pitch = contact.poly.poly_pitch
        self.nmos_fill = calculate_tx_metal_fill(nmos_width, self)
        self.pmos_fill = calculate_tx_metal_fill(pmos_width, self)
        self.poly_pitch = original_pitch

    def calculate_constraints(self):
        self.num_fingers = 2
        self.nmos_finger_width = utils.round_to_grid(self.size * self.min_tx_width / 2)
        self.pmos_finger_width = utils.round_to_grid(self.beta * self.size
                                                     * self.min_tx_width / 2)

        poly_rects = push_bitcell_array.bitcell.get_layer_shapes(POLY)
        self.poly_width = max([x.height for x in poly_rects])
        self.poly_pitch = self.poly_width + self.poly_space

    def add_poly_and_active(self, active_widths):
        self.poly_x_offset = self.implant_enclose_poly

        poly_to_mid_contact = 0.5 * contact.poly.first_layer_height

        self.gate_contact_x = (self.poly_x_offset + poly_to_mid_contact
                               - 0.5 * self.contact_width)
        self.pin_right_x = self.gate_contact_x + 0.5 * self.contact_width + 0.5 * self.m1_width
        self.n_active_x = self.pin_right_x + self.get_line_end_space(METAL1)
        self.n_active_right = self.n_active_x + self.nmos_finger_width

        self.p_active_x = self.n_active_right + 2 * self.implant_enclose_ptx_active
        self.p_active_right = self.p_active_x + self.pmos_finger_width

        self.poly_right_x = self.p_active_right + self.poly_extend_active

        if self.mirror:
            self.p_active_x = self.n_active_x
            self.p_active_right = self.p_active_x + self.pmos_finger_width
            self.n_active_x = self.p_active_right + 2 * self.implant_enclose_ptx_active
            self.n_active_right = self.n_active_x + self.nmos_finger_width

        self.active_height = ((self.num_fingers - 1) * self.poly_pitch
                              + self.poly_width + 2 * self.active_to_poly)

        self.poly_y = 0.5 * self.poly_space
        self.active_y = self.poly_y - self.active_to_poly

        x_offsets = [(self.n_active_x, self.n_active_right), (self.p_active_x, self.p_active_right)]
        active_rects = []
        for left, right in x_offsets:
            active_rects.append(self.add_rect(ACTIVE, offset=vector(left, self.active_y),
                                              width=right - left, height=self.active_height))
        self.nmos_active, self.pmos_active = active_rects

        y_offset = self.poly_y
        for i in range(2):
            self.add_rect(POLY, offset=vector(self.poly_x_offset, y_offset),
                          width=self.poly_right_x - self.poly_x_offset,
                          height=self.poly_width)
            y_offset += self.poly_pitch

        self.width = self.poly_right_x + self.implant_enclose_poly
        self.height = self.poly_y + self.poly_pitch + self.poly_width + 0.5 * self.poly_space

    def add_implants_and_nwell(self):
        if self.mirror:
            implant_offsets = [
                (self.n_active_x - self.implant_enclose_ptx_active, self.width),
                (0, self.p_active_right + self.implant_enclose_ptx_active)
            ]
            nwell_x = 0
            nwell_right = implant_offsets[1][1]
        else:
            implant_offsets = [
                (0, self.n_active_right + self.implant_enclose_ptx_active),
                (self.p_active_x - self.implant_enclose_ptx_active, self.width)
            ]
            nwell_x = implant_offsets[1][0]
            nwell_right = self.width
        implant_layers = [NIMP, PIMP]
        implant_bottom = self.active_y - self.implant_enclose_ptx_active
        implant_top = self.active_y + self.active_height + self.implant_enclose_ptx_active

        for i in range(2):
            self.add_rect(implant_layers[i], offset=vector(implant_offsets[i][0], implant_bottom),
                          width=implant_offsets[i][1] - implant_offsets[i][0],
                          height=implant_top - implant_bottom)

        well_enclosure = drc["well_extend_active"]
        well_bottom = self.active_y - well_enclosure
        well_top = self.active_y + self.active_height + well_enclosure
        self.add_rect(NWELL, offset=vector(nwell_x, well_bottom),
                      width=nwell_right - implant_offsets[1][0],
                      height=well_top - well_bottom)

    def get_poly_y_offsets(self, num_fingers):
        return [self.poly_y, self.poly_y + self.poly_pitch], [], []

    def connect_inputs(self):
        poly_y, _, _ = self.get_poly_y_offsets(self.num_fingers)
        for i in range(2):
            contact_y = poly_y[i]
            if i == 1:
                contact_y = contact_y + self.poly_width - self.contact_width
            self.add_rect(CONTACT, offset=vector(self.gate_contact_x, contact_y))
        if "min_medium_metal_via_extension" in drc:
            m1_extension = drc["min_medium_metal_via_extension"]
        else:
            m1_extension = utils.round_to_grid(0.5 * (contact.poly.second_layer_height
                                                      - contact.poly.contact_width))
        pin_y = poly_y[0] - m1_extension
        pin_width = self.get_drc_by_layer(METAL1, "line_end_threshold")
        pin_top = poly_y[1] + self.contact_width + m1_extension
        pin_x = self.pin_right_x - pin_width
        self.add_layout_pin("A", METAL1, offset=vector(pin_x, pin_y),
                            width=pin_width, height=pin_top - pin_y)

    def connect_outputs(self):
        if self.mirror:
            x_offset = self.pmos_active.cx()
        else:
            x_offset = self.nmos_active.cx()
        y_offset = self.nmos_active.cy() - 0.5 * self.m1_width
        self.add_layout_pin("Z", METAL1, offset=vector(x_offset, y_offset),
                            width=self.width - x_offset)

    def add_contact_fills(self):
        fill_props = ["nmos_fill", "pmos_fill"]
        active_rects = [self.nmos_active, self.pmos_active]
        for i in range(2):
            if getattr(self, fill_props[i]):
                fill_x, fill_right, fill_height, fill_width = getattr(self, fill_props[i])
                real_fill_x = fill_x + active_rects[i].lx()
                for y_offset in [-0.5 * fill_height, self.height - 0.5 * fill_height]:
                    self.add_rect(METAL1, offset=vector(real_fill_x, y_offset),
                                  width=fill_width, height=fill_height)

    def add_power_pins(self, layer=METAL3):
        self.rail_height = push_bitcell_array.bitcell.get_pins("gnd")[0].height()
        super().add_power_pins(layer)

    def connect_power(self):
        pin_names = ["gnd", "vdd"]
        actives = [self.nmos_active, self.pmos_active]
        via_shift = 0.5 * (m2m3.height - contact.well.height)
        for i in range(2):
            pin_name = pin_names[i]

            x_offset = actives[i].cx() + via_shift
            for y_offset in [0, self.height]:
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, y_offset),
                                        rotate=90)
            self.add_rect_center(METAL2, offset=vector(x_offset, actives[i].cy()),
                                 width=m1m2.height, height=self.height)

            pin = self.get_pin(pin_name)
            self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset, pin.cy()),
                                    rotate=90)
