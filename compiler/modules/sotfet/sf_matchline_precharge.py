import debug
from base import utils
from base.contact import contact, m1m2, poly as poly_contact, active as active_contact
from base.design import design
from base.vector import vector
from globals import OPTS
from modules import body_tap
from pgates.ptx_spice import ptx_spice
from tech import parameter, drc


class sf_matchline_precharge(design):
    """
    vdd pin -> active -> poly contacts -> ml rail -> gnd pin
    """

    bitcell = None
    test_contact = None

    def __init__(self, size=1):
        design.__init__(self, "matchline_precharge")
        debug.info(2, "Create matchline_precharge with size {}".format(size))

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell = self.mod_bitcell()

        self.separate_vdd = OPTS.separate_vdd if hasattr(OPTS, 'separate_vdd') else False

        self.beta = parameter["beta"]
        size *= OPTS.word_size/64.0
        self.ptx_width = size * self.beta * parameter["min_tx_size"]
        self.height = self.bitcell.height

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        # From below:
        self.calculate_fingers()
        self.add_ptx()
        self.add_poly()
        self.add_nwell_contact()

        self.add_active()
        self.add_implants()

        self.add_gnd_pin()

        self.route_source_drain()
        self.add_ml_pin()

        self.add_chb_pin()

    def add_pins(self):
        nwell_pin = ["decoder_vdd"] if self.separate_vdd else []
        self.add_pin_list(["chb", "ml", "vdd", "gnd"] + nwell_pin)

    def add_poly(self):
        self.poly_y_offset = self.bottom_space
        layers = 2*["po_dummy"] + ["poly"]*self.tx_mults + 2*["po_dummy"]

        poly_height = self.ptx_width + self.poly_extend_active + self.active_to_poly_contact_center + \
                      0.5*poly_contact.height

        poly_positions = []  # left edge of polys
        x_offset = -0.5*self.poly_width
        for layer in layers:
            poly_positions.append(x_offset)
            self.add_rect(layer, width=self.poly_width, height=poly_height, offset=vector(x_offset, self.poly_y_offset))
            x_offset += self.poly_pitch

        self.width = x_offset + 0.5*self.poly_width - self.poly_pitch

        self.real_poly_pos = poly_positions[2:-2]
        self.poly_contact_y_offset = (self.poly_y_offset + self.poly_extend_active +
                                      self.ptx_width + self.active_to_poly_contact_center)
        for x_offset in self.real_poly_pos:
            self.add_contact_center(layers=poly_contact.layer_stack, offset=vector(x_offset + 0.5*self.poly_width,
                                                                                   self.poly_contact_y_offset))
        # connect gate contacts
        x_offset = self.real_poly_pos[0] + 0.5*self.poly_width - 0.5*self.m1_width
        x_offset2 = self.real_poly_pos[-1] + 0.5*self.poly_width + 0.5*self.m1_width
        y_offset = self.poly_contact_y_offset-0.5*poly_contact.second_layer_height
        self.add_rect("metal1", offset=vector(x_offset, y_offset),
                      height=poly_contact.second_layer_height, width=x_offset2 - x_offset)
        # min m1 drc
        if self.tx_mults == 1:
            m1_height = poly_contact.second_layer_height
            m1_width = utils.ceil(drc["minarea_metal1_contact"]/m1_height)
            self.add_rect_center("metal1", offset=vector(self.mid_x, y_offset + 0.5*m1_height), height=m1_height,
                                 width=m1_width)

        self.gate_contact_top = y_offset + poly_contact.second_layer_height

    def add_active(self):
        self.active_y_offset = self.poly_y_offset + self.poly_extend_active
        active_enclose_contact = drc["active_enclosure_contact"]
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate
        self.active_width = 2 * self.end_to_poly + self.tx_mults * self.poly_pitch - self.poly_space

        x_offset = self.mid_x - 0.5*self.active_width

        self.add_rect("active", offset=vector(x_offset, self.active_y_offset), width=self.active_width,
                      height=self.ptx_width)

    def add_nwell_contact(self):
        # add vdd rail
        rail_height = self.bitcell.get_pin("gnd").height()
        self.add_layout_pin("vdd", "metal1", width=self.width-self.line_end_space, height=rail_height,
                            offset=vector(0, -0.5 * rail_height))
        if self.separate_vdd:
            return

        min_active_width = max(utils.ceil(drc["minarea_cont_active_thin"] / self.well_contact_active_height),
                               2*self.contact_width + 2 *drc["active_enclosure_contact"] + self.contact_spacing)

        self.add_rect_center("active", offset=vector(self.mid_x, 0), width=min_active_width,
                             height=self.well_contact_active_height)
        self.add_rect("nimplant", offset=vector(0, -0.5*self.well_contact_implant_height), width=self.width,
                      height=self.well_contact_implant_height)

        x_offsets = [0.5*(self.width - self.contact_spacing - self.contact_width),
                     0.5*(self.width + self.contact_spacing + self.contact_width)]
        for x_offset in x_offsets:
            self.add_rect_center("contact", offset=vector(x_offset, 0))

    def add_implants(self):
        # get body tap implant
        tap = body_tap.body_tap()
        tap_implant = self.get_gds_layer_shapes(tap, "pimplant")[0]
        tap_implant_x = tap_implant[0][0]

        self.add_rect("pimplant", offset=vector(0, 0.5*self.well_contact_implant_height),
                      width=self.width + tap_implant_x, height=self.height - 0.5*self.well_contact_implant_height)
        nwell_y = - self.well_enclose_active - 0.5*self.well_contact_active_height
        self.add_rect("nwell", offset=vector(0, nwell_y), width=self.width,
                      height=self.height - nwell_y)
        
    def add_ml_pin(self):
        y_offset = self.active_y_offset + 0.5*self.ptx_width - 0.5*self.test_contact.second_layer_height
        self.add_layout_pin("ml", "metal1",
                            offset=vector(self.source_positions[-1]-0.5*self.test_contact.width, y_offset),
                            width=self.test_contact.width, height=self.test_contact.second_layer_height)

    def add_gnd_pin(self):
        gnd_pin = self.bitcell.get_pin("gnd")
        self.add_layout_pin("gnd", gnd_pin.layer, offset=vector(0, gnd_pin.by()), height=gnd_pin.height(),
                            width=self.width)

    def calculate_fingers(self):
        gnd_pin = self.bitcell.get_pin("gnd")

        self.active_to_poly_contact_center = self.line_end_space + 0.5 * poly_contact.second_layer_height

        extra_poly = self.poly_extend_active + self.active_to_poly_contact_center + 0.5 * poly_contact.height

        self.tx_mults = 1
        while True:
            self.width = (3 + self.tx_mults)*self.poly_pitch
            self.well_contact_implant_height = max(utils.ceil(drc["minarea_implant"] / self.width),
                                                   drc["minwidth_implant"])
            self.bottom_space = self.poly_to_active + 0.5 * self.well_contact_implant_height

            total_space = (self.bottom_space + extra_poly + 0.5 * gnd_pin.height() + self.m1_space)
            max_active_height = self.bitcell.height - total_space

            if self.tx_mults * max_active_height > self.ptx_width:
                break
            else:
                self.tx_mults += 1

        self.well_contact_active_height = max(self.well_contact_implant_height - 2*self.implant_enclose_active,
                                              active_contact.first_layer_width)
        self.mid_x = 0.5*self.width

        self.ptx_width = utils.round_to_grid(self.ptx_width / self.tx_mults)

    def add_ptx(self):
        self.ptx = ptx_spice(width=self.ptx_width, mults=self.tx_mults, tx_type="pmos")
        self.add_mod(self.ptx)
        self.ptx_inst = self.add_inst("ptx", mod=self.ptx, offset=vector(0, 0))
        nwell_vdd = "decoder_vdd" if self.separate_vdd else "vdd"
        self.connect_inst(["ml", "chb", "vdd", nwell_vdd])

    def route_source_drain(self):
        num_contacts = self.calculate_num_contacts(self.ptx_width)
        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        contact_x_start = (self.mid_x - 0.5*self.active_width + drc["active_enclosure_contact"]
                           + 0.5*self.contact_width)

        # calculate mid_x positions of source and drain contacts
        source_positions = [contact_x_start]
        drain_positions = []

        active_mid_y = self.active_y_offset + 0.5*self.ptx_width

        for i in range(self.tx_mults):
            x_offset = contact_x_start + (i + 1) * self.contact_pitch

            if i % 2 == 0:
                drain_positions.append(x_offset)
            else:
                source_positions.append(x_offset)
        if self.tx_mults % 2 == 1:  # ml pin should be to the right so we can connect to bitcell using M1
            self.source_positions = drain_positions
            self.drain_positions = source_positions
        else:
            self.source_positions = source_positions
            self.drain_positions = drain_positions

        for x_offset in self.source_positions + self.drain_positions:
            self.add_contact_center(contact.active_layers, offset=vector(x_offset, active_mid_y),
                                    size=(1, num_contacts))

        self.test_contact = test_contact = contact(layer_stack=poly_contact.layer_stack,
                                                   dimensions=[1, num_contacts])
        if self.tx_mults > 1:

            for x_offset in self.source_positions:
                self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset, active_mid_y))

            # check height of contacts

                if test_contact.second_layer_width * test_contact.second_layer_height < drc["minarea_metal1_contact"]:
                    # min m1 drc area
                    fill_width = 2*(self.contact_pitch - 0.5*self.m1_width - self.m1_space)
                    fill_height = utils.ceil(drc["minarea_metal1_contact"]/fill_width)
                    if fill_height < test_contact.second_layer_height:
                        fill_height = test_contact.second_layer_height
                        fill_width = max(utils.ceil(drc["minarea_metal1_contact"]/fill_height), self.m1_width)
                    self.add_rect_center("metal1", offset=vector(x_offset, active_mid_y), width=fill_width,
                                         height=fill_height)

        # connect sources using m2
        if self.tx_mults > 1:
            self.add_rect("metal2", offset=vector(self.source_positions[0], active_mid_y-0.5*self.m2_width),
                          width=self.source_positions[-1] - self.source_positions[0])
        # drain to vdd
        for x_offset in self.drain_positions:
            self.add_rect("metal1", offset=vector(x_offset-0.5*self.m1_width, 0), height=active_mid_y)

    def add_chb_pin(self):
        x_offset = max(self.source_positions + self.drain_positions) + self.parallel_line_space + 0.5*self.m2_width
        self.add_layout_pin("chb", "metal2", offset=vector(x_offset, 0), height=self.height)
        self.add_rect("metal2", offset=vector(self.real_poly_pos[-1], self.poly_contact_y_offset-0.5*self.m2_width),
                      width=x_offset-self.real_poly_pos[-1])
        if self.tx_mults == 1:
            self.add_contact_center(m1m2.layer_stack, offset=vector(self.real_poly_pos[0], self.poly_contact_y_offset),
                                    rotate=90)
        else:
            self.add_contact_center(m1m2.layer_stack,
                offset=vector(self.real_poly_pos[-1] - 0.5*(m1m2.first_layer_height-self.m2_width+self.poly_width),
                              self.poly_contact_y_offset), rotate=90)










