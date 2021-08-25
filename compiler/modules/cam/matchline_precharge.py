import debug
from base import utils
from base.contact import m1m2, poly as poly_contact, active as active_contact
from base.design import design, METAL1, METAL2, NIMP, ACTIVE, PIMP, NWELL, POLY, PO_DUMMY
from base.vector import vector
from base.well_active_contacts import calculate_num_contacts
from base.well_implant_fills import calculate_tx_metal_fill
from globals import OPTS
from modules.precharge import precharge_characterization
from pgates.ptx_spice import ptx_spice
from tech import parameter, drc, add_tech_layers


class MatchlinePrecharge(precharge_characterization, design):
    """
    vdd pin -> active -> poly contacts -> ml rail -> gnd pin
    """

    bitcell = None
    test_contact = None

    def __init__(self, size=1, name=None):
        name = name or "matchline_precharge"
        design.__init__(self, name)
        debug.info(2, "Create matchline_precharge with size {}".format(size))

        self.bitcell = self.create_mod_from_str(OPTS.bitcell)

        self.beta = parameter["beta"]
        self.size = size
        self.ptx_width = size * self.beta * parameter["min_tx_size"]
        self.height = self.bitcell.height

        self.create_layout()
        self.add_boundary()

    def create_layout(self):
        self.add_pins()
        # From below:
        self.calculate_fingers()
        self.add_ptx_spice()

        self.add_nwell_contact()

        self.add_poly()
        self.add_active()

        self.add_implants()

        self.add_gnd_pin()
        self.route_source_drain()

        self.add_precharge_pin()
        self.add_ml_pin()

        add_tech_layers(self)

    def add_pins(self):
        self.add_pin_list(["precharge_en_bar", "ml", "vdd", "gnd"])

    def calculate_width(self, num_fingers):

        active_width = 2 * self.end_to_poly + num_fingers * self.poly_pitch - self.poly_space
        self.active_width = active_width

        # add space for enable pin
        self.active_space = self.get_space_by_width_and_length(ACTIVE,
                                                               max_width=active_width)
        width = (active_width + self.get_parallel_space(METAL2) +
                 self.bus_width + self.active_space)
        # check for dummy
        if not self.has_dummy:
            return width
        width_by_poly = (2 * self.num_poly_dummies - 1 + num_fingers) * self.poly_pitch

        return max(width_by_poly, width)

    def calculate_fingers(self):

        active_enclose_contact = max(drc["active_enclosure_contact"],
                                     (self.active_width - self.contact_width) / 2)
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate

        self.active_to_poly_contact_center = (self.line_end_space +
                                              0.5 * poly_contact.second_layer_height)

        self.gnd_rail_height = self.rail_height

        self.bottom_space = 0.5 * self.gnd_rail_height + self.get_line_end_space(METAL1)

        extra_poly = (self.poly_extend_active + self.active_to_poly_contact_center +
                      0.5 * poly_contact.height)

        self.tx_mults = 1

        while True:
            self.width = self.calculate_width(self.tx_mults)

            _, implant_height = self.calculate_min_area_fill(self.width,
                                                             layer=NIMP)
            active_width = self.width - 2 * self.well_enclose_active
            active_area = drc.get("minarea_cont_active_thin", self.get_min_area(ACTIVE))

            active_height = max(active_contact.first_layer_width,
                                utils.ceil(active_area / active_width))
            self.well_contact_active_height = active_height

            implant_height = max(implant_height, active_height + 2 * self.implant_enclose_active)

            self.well_contact_implant_height = implant_height

            total_space = (extra_poly + self.bottom_space + 0.5 * active_height +
                           self.poly_to_active)
            max_active_height = self.bitcell.height - total_space

            if self.tx_mults * max_active_height > self.ptx_width:
                break
            else:
                self.tx_mults += 1

        ac_height = max(self.well_contact_implant_height - 2 * self.implant_enclose_active,
                        active_contact.first_layer_width)
        self.well_contact_active_height = ac_height

        self.ptx_width = utils.round_to_grid(max(self.ptx_width / self.tx_mults,
                                                 self.min_tx_width))

    def add_poly(self):
        num_dummy = self.num_poly_dummies
        layers = num_dummy * [PO_DUMMY] + [POLY] * self.tx_mults + num_dummy * [PO_DUMMY]

        poly_height = (self.ptx_width + self.poly_extend_active +
                       self.active_to_poly_contact_center +
                       0.5 * poly_contact.height)

        self.poly_y_offset = (self.height - 0.5 * self.well_contact_active_height -
                              self.poly_to_active - poly_height)

        poly_positions = []  # left edge of polys

        if num_dummy > 0:
            x_offset = -0.5 * self.poly_width
        else:
            x_offset = self.active_space + self.end_to_poly
            if self.has_pwell:
                x_offset = max(x_offset, self.well_enclose_ptx_active + self.end_to_poly)

        for layer in layers:
            poly_positions.append(x_offset)
            self.add_rect(layer, width=self.poly_width, height=poly_height,
                          offset=vector(x_offset, self.poly_y_offset))
            x_offset += self.poly_pitch

        if num_dummy > 0:
            self.real_poly_pos = poly_positions[num_dummy:-num_dummy]
        else:
            self.real_poly_pos = poly_positions
        self.poly_contact_y_offset = self.poly_y_offset + 0.5 * poly_contact.height
        for x_offset in self.real_poly_pos:
            self.add_contact_center(layers=poly_contact.layer_stack,
                                    offset=vector(x_offset + 0.5 * self.poly_width,
                                                  self.poly_contact_y_offset))
        # connect gate contacts
        x_offset = self.real_poly_pos[0] + 0.5 * self.poly_width - 0.5 * self.m1_width
        x_offset2 = self.real_poly_pos[-1] + 0.5 * self.poly_width + 0.5 * self.m1_width
        y_offset = self.poly_contact_y_offset - 0.5 * poly_contact.second_layer_height
        self.add_rect(METAL1, offset=vector(x_offset, y_offset),
                      height=poly_contact.second_layer_height, width=x_offset2 - x_offset)
        # min m1 drc
        if self.tx_mults == 1:
            m1_height = poly_contact.second_layer_height
            _, m1_width = self.calculate_min_area_fill(m1_height, layer=METAL1)
            if m1_width:
                x_offset = self.real_poly_pos[0] + 0.5 * self.poly_width
                self.add_rect_center(METAL1, offset=vector(x_offset, y_offset + 0.5 * m1_height),
                                     height=m1_height, width=m1_width)

        self.gate_contact_top = y_offset + poly_contact.second_layer_height

    def add_active(self):
        self.active_y_offset = (self.poly_y_offset + self.active_to_poly_contact_center +
                                0.5 * poly_contact.height)

        if self.num_poly_dummies > 0:
            x_offset = (self.num_poly_dummies * self.poly_pitch - 0.5 * self.poly_width -
                        self.end_to_poly)
        else:
            x_offset = self.real_poly_pos[0] - self.end_to_poly

        self.active_rect = self.add_rect("active", offset=vector(x_offset, self.active_y_offset),
                                         width=self.active_width, height=self.ptx_width)

    def add_nwell_contact(self):
        # add vdd rail
        rail_height = self.rail_height
        self.add_layout_pin("vdd", METAL1, width=self.width, height=rail_height,
                            offset=vector(0, self.height - 0.5 * rail_height))

        active_width = self.width - 2 * self.well_enclose_active
        active_height = self.well_contact_active_height

        self.add_rect_center(ACTIVE, offset=vector(0.5 * self.width, self.height),
                             width=active_width, height=active_height)

        self.add_rect(NIMP, offset=vector(0, self.height - 0.5 * self.well_contact_implant_height),
                      width=self.width, height=self.well_contact_implant_height)

        cont = calculate_num_contacts(self, active_width, return_sample=True)
        self.add_inst(cont.name, cont, offset=vector(0.5 * (self.width + cont.height),
                                                     self.height - 0.5 * cont.width), rotate=90)
        self.connect_inst([])

    def add_implants(self):
        # get body tap implant
        if OPTS.use_x_body_taps:
            tap = self.create_mod_from_str(OPTS.body_tap)
            tap_implant = self.get_gds_layer_shapes(tap, PIMP)[0]
            tap_implant_x = tap_implant[0][0]
        else:
            tap_implant_x = 0

        self.add_rect(PIMP, offset=vector(0, 0),
                      width=self.width + tap_implant_x,
                      height=self.height - 0.5 * self.well_contact_implant_height)
        nwell_height = (self.height + 0.5 * self.well_contact_active_height +
                        self.well_enclose_active)

        if self.has_pwell:
            x_offset = min(0, self.active_rect.lx() - self.well_enclose_ptx_active)
        else:
            x_offset = -self.well_enclose_active
        nwell_width = self.width + self.well_enclose_active - x_offset
        self.add_rect(NWELL, offset=vector(x_offset, 0), width=nwell_width,
                      height=nwell_height)

    def add_gnd_pin(self):
        if "gnd" not in self.bitcell.pins:
            return
        gnd_pin = self.bitcell.get_pins("gnd")[0]
        self.add_layout_pin("gnd", gnd_pin.layer, offset=vector(0, -0.5 * self.gnd_rail_height),
                            height=self.gnd_rail_height, width=self.width)

    def add_ptx_spice(self):
        self.ptx = self.pmos = ptx_spice(width=self.ptx_width,
                                         mults=self.tx_mults, tx_type="pmos")
        self.add_mod(self.ptx)
        self.ptx_inst = self.add_inst("ptx", mod=self.ptx, offset=vector(0, 0))
        self.connect_inst(["ml", "precharge_en_bar", "vdd", "vdd"])

    def route_source_drain(self):
        cont = self.calculate_num_contacts(self.ptx_width, return_sample=True)
        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        contact_x_start = self.real_poly_pos[0] - 0.5 * self.contact_width - self.contact_to_gate

        # calculate mid_x positions of source and drain contacts
        source_positions = []
        drain_positions = []

        active_mid_y = self.active_rect.cy()

        for i in range(self.tx_mults + 1):
            x_offset = contact_x_start + i * self.contact_pitch

            cont_offset = vector(x_offset - 0.5 * cont.width,
                                 active_mid_y - 0.5 * cont.height)
            self.add_inst(cont.name, cont, offset=cont_offset)
            self.connect_inst([])

            if i % 2 == 1:
                drain_positions.append(x_offset)
            else:
                source_positions.append(x_offset)
        if self.tx_mults % 2 == 1:  # ml pin should be to the right so we can connect to bitcell using M1
            self.source_positions = drain_positions
            self.drain_positions = source_positions
        else:
            self.source_positions = source_positions
            self.drain_positions = drain_positions

        # add metal fills
        fill = calculate_tx_metal_fill(self.ptx_width, self, contact_if_none=False)
        if fill:
            y_offset, _, fill_width, fill_height = fill
            for x_offset in self.source_positions:
                offset = vector(x_offset - 0.5 * fill_width, self.active_rect.by() +
                                y_offset)
                self.add_rect(METAL1, offset=offset,
                              width=fill_width, height=fill_height)

        if self.tx_mults > 1:
            num_m1m2 = max(1, cont.dimensions[1] - 1)
            for x_offset in self.source_positions:
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, active_mid_y),
                                        size=(1, num_m1m2))
            # connect sources using m2
            self.add_rect(METAL2, offset=vector(self.source_positions[0],
                                                active_mid_y - 0.5 * self.m2_width),
                          width=self.source_positions[-1] - self.source_positions[0])
        # drain to vdd
        for x_offset in self.drain_positions:
            self.add_rect(METAL1,
                          offset=vector(x_offset - 0.5 * self.m1_width, active_mid_y),
                          height=self.height - active_mid_y)

        self.source_contact = cont

    def add_ml_pin(self):

        y_offset = self.active_rect.cy() - 0.5 * self.source_contact.height
        x_offset = self.source_positions[-1]

        self.add_layout_pin("ml", METAL1,
                            offset=vector(x_offset - 0.5 * self.source_contact.width, y_offset),
                            width=self.source_contact.width,
                            height=self.source_contact.second_layer_height)

    def add_precharge_pin(self):
        x_offset = self.active_rect.rx() + self.get_parallel_space(METAL2)
        self.add_layout_pin("precharge_en_bar", METAL2,
                            offset=vector(x_offset, 0), height=self.height,
                            width=self.bus_width)
        self.add_rect(METAL2, offset=vector(self.real_poly_pos[-1],
                                            self.poly_contact_y_offset - 0.5 * self.m2_width),
                      width=x_offset - self.real_poly_pos[-1])
        if self.tx_mults == 1:
            self.add_contact_center(m1m2.layer_stack, offset=vector(self.real_poly_pos[0],
                                                                    self.poly_contact_y_offset),
                                    rotate=90)
        else:
            offset = vector(self.real_poly_pos[-1] - 0.5 * (
                    m1m2.first_layer_height - self.m2_width + self.poly_width),
                            self.poly_contact_y_offset)
            self.add_contact_center(m1m2.layer_stack, offset=offset, rotate=90)
