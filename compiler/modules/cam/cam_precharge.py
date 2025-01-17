import debug
from base import utils
from base.contact import cross_m2m3, cross_m1m2, m1m2, poly as poly_contact
from base.design import design, NIMP, POLY, PIMP, METAL2, METAL3, METAL1, ACTIVE, PWELL, NWELL
from base.vector import vector
from base.well_active_contacts import get_max_contact, calculate_num_contacts
from globals import OPTS
from modules.precharge import precharge_characterization
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice
from tech import parameter, add_tech_layers


class CamPrecharge(precharge_characterization, design):

    def __init__(self, name, size=1, has_precharge=True):
        design.__init__(self, name)
        debug.info(2, "create single precharge cell: {0}".format(name))

        self.bitcell = self.create_mod_from_str(OPTS.bitcell)

        self.size = size
        self.beta = parameter["beta"]

        self.ptx_width = utils.round_to_grid(size * self.beta * parameter["min_tx_size"])
        self.size = self.ptx_width / (self.beta * parameter["min_tx_size"])
        self.width = self.bitcell.width
        self.has_precharge = has_precharge

        self.add_pins()
        self.create_layout()
        self.add_boundary()
        self.DRC_LVS()

    def add_pins(self):
        precharge_en_bar = ["precharge_en_bar"] * self.has_precharge
        vdd = ["vdd"] * self.has_precharge
        pins = (["bl", "br"] + precharge_en_bar + ["discharge"] + vdd + ["gnd"])
        self.add_pin_list(pins)

    def create_layout(self):
        self.create_modules()
        self.setup_layout_constants()
        self.add_spice_connections()
        self.add_modules()
        self.add_enable_pins()
        self.add_bitlines()
        self.connect_power()
        self.add_body_taps()
        self.extend_wells()
        add_tech_layers(self)

    def create_modules(self):
        """Create 3 finger nmos and pmos"""
        self.nmos_width = utils.round_to_grid(self.size * parameter["min_tx_size"])
        self.nmos = ptx(tx_type="nmos", width=self.nmos_width, connect_poly=True, mults=3)
        self.add_mod(self.nmos)

        self.pmos_width = utils.round_to_grid(self.nmos_width * self.beta)
        self.pmos = ptx(tx_type="pmos", width=self.pmos_width, connect_poly=True, mults=3)
        self.add_mod(self.pmos)

    def setup_layout_constants(self):
        """Calculate layout dimensions and offsets"""
        self.mid_x = utils.round_to_grid(0.5 * self.width)

        contact_implant_height = self.implant_width
        contact_active_height = max(contact_implant_height - 2 * self.implant_enclose_active,
                                    self.active_width)
        contact_implant_height = max(contact_implant_height,
                                     contact_active_height + 2 * self.implant_enclose_active)

        nmos_implant = self.nmos.get_layer_shapes(NIMP)[0]
        nmos_poly = min(self.nmos.get_layer_shapes(POLY), key=lambda x: x.by())
        # nmos_y
        self.nmos_y = max(contact_implant_height - nmos_implant.by(),
                          contact_active_height + self.poly_to_active - nmos_poly.by())

        self.contact_active_height = contact_active_height
        self.contact_implant_height = contact_implant_height

        if not self.has_precharge:
            nmos_gate_y = self.nmos_y + self.nmos.get_pins("G")[0].cy()
            via_height = max(poly_contact.height, cross_m2m3.first_layer_height)
            bitline_bot = nmos_gate_y + 0.5 * via_height

            bitcell_pin = self.bitcell.get_pin("bl")

            self.height = (bitline_bot + self.get_line_end_space(METAL2) +
                           bitcell_pin.width())
            self.nwell_cont_y = None
            return

        pmos_implant = self.pmos.get_layer_shapes(PIMP)[0]
        pmos_poly = min(self.pmos.get_layer_shapes(POLY), key=lambda x: x.by())

        # pmos_y by poly
        pmos_y = (self.nmos_y + nmos_poly.uy() + self.poly_vert_space - pmos_poly.by())
        # pmos_y by poly contacts
        m1_poly_ext = utils.ceil(0.5 * (poly_contact.second_layer_height -
                                        poly_contact.first_layer_height))
        pmos_y = max(pmos_y, pmos_y + 2 * m1_poly_ext)

        # pmos_y by implant
        pmos_y = max(pmos_y, self.nmos_y + nmos_implant.uy() - pmos_implant.by())
        self.pmos_y = pmos_y

        # nwell contact
        pimp_top = self.pmos_y + pmos_implant.uy()
        poly_top = self.pmos_y + pmos_poly.uy()

        self.nwell_cont_y = max(pimp_top,
                                poly_top + self.poly_to_active + self.implant_enclose_active)

        self.height = self.nwell_cont_y + self.contact_implant_height

    def add_modules(self):
        """Add pmos and nmos"""
        x_offset = self.mid_x - 0.5 * self.nmos.width
        self.nmos_inst = self.add_inst("discharge", self.nmos,
                                       offset=vector(x_offset, self.nmos_y))
        self.connect_inst([], check=False)
        self.ptx_insts = [self.nmos_inst]
        if not self.has_precharge:
            return

        self.pmos_inst = self.add_inst("precharge", self.pmos,
                                       offset=vector(x_offset, self.pmos_y))
        self.connect_inst([], check=False)
        self.ptx_insts.append(self.pmos_inst)

    def add_spice_connections(self):
        """Create spice connections"""
        widths = [self.nmos_width, self.pmos_width]
        enables = ["discharge", "precharge_en_bar"]
        power_nets = ["gnd", "vdd"]
        tx_types = ["nmos", "pmos"]

        num_insts = 2 if self.has_precharge else 1

        for i in range(num_insts):
            spice_obj = ptx_spice(tx_type=tx_types[i], width=widths[i], mults=1)
            names = ["equalizer", "bl", "br"]
            for j in range(3):
                self.add_inst(name=f"{names[j]}_{tx_types[i]}", mod=spice_obj,
                              offset=vector(0, 0))
            power = power_nets[i]
            self.connect_inst(["bl", enables[i], "br", power], check=False)
            self.connect_inst(["bl", enables[i], power, power], check=False)
            self.connect_inst(["br", enables[i], power, power], check=True)

    def add_enable_pins(self):
        pin_names = ["discharge", "precharge_en_bar"]
        insts = self.ptx_insts

        fill_height = cross_m2m3.height
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)

        pin_x = - 0.5 * cross_m2m3.height
        for i in range(len(self.ptx_insts)):
            gate_pin = insts[i].get_pin("G")
            self.add_layout_pin(pin_names[i], METAL3,
                                offset=vector(pin_x, gate_pin.cy() - 0.5 * self.bus_width),
                                width=self.width - pin_x, height=self.bus_width)
            self.add_cross_contact_center(cross_m2m3, offset=vector(0, gate_pin.cy()))
            self.add_cross_contact_center(cross_m1m2, offset=vector(0, gate_pin.cy()),
                                          rotate=90)
            self.add_rect(METAL1, offset=vector(0, gate_pin.by()),
                          width=gate_pin.lx(), height=gate_pin.height())
            if fill_width:
                self.add_rect_center(METAL2, offset=vector(0, gate_pin.cy()),
                                     width=fill_width, height=fill_height)

    @staticmethod
    def get_bitline_drain_source_indices():
        return [1, 2]

    def get_bitline_width(self):
        # calculate max bitline width
        sample_pin = self.bitcell.get_pin("bl")
        m2_space = self.get_parallel_space(METAL2)
        bitline_width = min(sample_pin.width(),
                            0.5 * self.width - 0.5 * m1m2.width - m2_space - sample_pin.lx())
        return utils.floor(bitline_width)

    def fill_source_drain(self, pin_name, tx_pin, tx_inst, pin_contact, layer):

        # calculate fills
        fill_edge_to_mid_cont = 0.5 * (self.poly_pitch - self.get_parallel_space(layer))
        active_width = self.nmos.get_layer_shapes(ACTIVE)[0].width
        fill_width = 0.5 * (active_width - 3 * self.get_parallel_space(layer) -
                            2 * m1m2.first_layer_width)
        fill_height = utils.ceil(self.get_min_area(METAL1) / fill_width)
        # add m1 fill
        if fill_height > self.m1_width:
            if tx_inst == self.nmos_inst:
                y_offset = pin_contact.uy() - fill_height
            else:
                y_offset = pin_contact.by()
            if pin_name == "bl":
                x_offset = tx_pin.cx() + fill_edge_to_mid_cont - fill_width
            else:
                x_offset = tx_pin.cx() - fill_edge_to_mid_cont

            self.add_rect(layer, offset=vector(x_offset, y_offset),
                          width=fill_width, height=fill_height)

    def add_bitlines(self):
        bitline_width = self.get_bitline_width()

        pin_names = ["bl", "br"]
        pin_indices = self.get_bitline_drain_source_indices()
        for i in range(2):
            pin_name = pin_names[i]
            bitcell_pin = self.bitcell.get_pin(pin_name)

            tx_pins = []
            contacts = []

            for tx in self.ptx_insts:
                source_drain = tx.get_pins("S") + tx.get_pins("D")
                tx_pin = list(sorted(source_drain, key=lambda x: x.lx()))[pin_indices[i]]
                tx_pins.append(tx_pin)

                # add m1m2 contact
                active_rect = max(tx.mod.get_layer_shapes(ACTIVE), key=lambda x: x.height)
                cont = get_max_contact(layer_stack=m1m2.layer_stack, height=active_rect.height)

                offset = vector(tx_pin.cx() - 0.5 * cont.width,
                                tx_pin.cy() - 0.5 * cont.height)
                contacts.append(self.add_inst(cont.name, cont, offset=offset))
                self.connect_inst([])
                self.fill_source_drain(pin_name, tx_pin, tx, contacts[-1], METAL1)

            # join nmos pmos
            if self.has_precharge:
                y_top = tx_pins[1].cy()
            else:
                y_top = self.height
            offset = vector(tx_pins[0].cx() - 0.5 * cont.width, tx_pins[0].cy())
            self.add_rect(METAL2, offset=offset, width=cont.second_layer_width,
                          height=y_top - offset.y)
            # create pins and join to nmos drains
            bottom_cont = contacts[0]
            x_offset = bitcell_pin.lx() if i == 0 else bitcell_pin.rx() - bitline_width
            self.add_layout_pin(pin_name, METAL2, offset=vector(x_offset, 0),
                                width=bitline_width,
                                height=bottom_cont.by() + bitline_width)
            self.add_rect(METAL2, offset=vector(x_offset, bottom_cont.by()),
                          width=tx_pins[0].cx() - x_offset,
                          height=bitline_width)

            # extend pmos pins to vdd
            if self.has_precharge:
                top_cont = contacts[1]
                y_offset = top_cont.uy() - bitline_width
                self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                              width=bitline_width,
                              height=self.height - y_offset)
            else:
                y_offset = self.height - bitline_width

            rect_edge = bitcell_pin.lx() if i == 0 else bitcell_pin.rx()

            self.add_rect(METAL2, offset=vector(rect_edge, y_offset),
                          width=tx_pins[0].cx() - rect_edge,
                          height=bitline_width)

    def get_rail_height(self):
        return max(self.rail_height, self.contact_implant_height)

    def connect_power(self):
        rail_height = self.get_rail_height()
        y_offsets = [0.5 * self.contact_implant_height - 0.5 * rail_height,
                     self.height - 0.5 * self.contact_implant_height + 0.5 * rail_height]
        for i, tx in enumerate(self.ptx_insts):
            source_drain = list(sorted(tx.get_pins("S") + tx.get_pins("D"),
                                       key=lambda x: x.lx()))
            for pin_index in [0, 3]:
                pin = source_drain[pin_index]
                self.add_rect(METAL1, offset=vector(pin.lx(), pin.cy()),
                              width=pin.width(), height=y_offsets[i] - pin.cy())

    def add_body_taps(self):
        rail_height = self.get_rail_height()
        fill_height = rail_height
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)

        sample = calculate_num_contacts(self, self.width, return_sample=True)
        cont_x = 0.5 * self.width + 0.5 * sample.height
        pin_names = ["gnd", "vdd"]
        implants = [PIMP, NIMP]
        y_offsets = [0, self.nwell_cont_y]
        for i in range(len(self.ptx_insts)):
            mid_y = y_offsets[i] + 0.5 * self.contact_implant_height

            cont_y = mid_y - 0.5 * sample.width
            self.add_inst(sample.name, sample, offset=vector(cont_x, cont_y),
                          rotate=90)
            self.connect_inst([])

            rail_y = mid_y - 0.5 * rail_height

            for layer in [METAL1, METAL3]:
                self.add_layout_pin(pin_names[i], layer, offset=vector(0, rail_y),
                                    width=self.width, height=rail_height)
            via_offset = vector(0.5 * self.width, mid_y)
            self.add_cross_contact_center(cross_m1m2, via_offset, rotate=True)
            self.add_cross_contact_center(cross_m2m3, via_offset, rotate=False)
            if fill_width:
                self.add_rect_center(METAL2, offset=via_offset,
                                     width=fill_width, height=fill_height)

            self.add_rect_center(implants[i], offset=via_offset,
                                 width=self.width + 2 * self.implant_enclose_active,
                                 height=self.contact_implant_height)
            self.add_rect_center(ACTIVE, offset=via_offset,
                                 height=self.contact_active_height,
                                 width=self.width)

    def extend_wells(self):
        extension = self.well_enclose_active
        x_offsets = [-extension, self.width + extension]
        y_offsets = [-extension, self.height + extension]
        layers = [PWELL, NWELL]
        implants = [NIMP, PIMP]
        all_tx = self.ptx_insts

        for i in range(len(all_tx)):
            implant_rect = max(all_tx[i].get_layer_shapes(implants[i]),
                               key=lambda x: x.width * x.height)
            self.add_rect(implants[i], offset=vector(0, implant_rect.by()),
                          width=self.width, height=implant_rect.height)
            if i == 0 and not self.has_pwell:
                continue
            well_rect = max(all_tx[i].get_layer_shapes(layers[i]),
                            key=lambda x: x.width * x.height)
            target_y = well_rect.uy() if i == 0 else well_rect.by()

            self.add_rect(layers[i], offset=vector(x_offsets[0], target_y),
                          width=x_offsets[1] - x_offsets[0],
                          height=y_offsets[i] - target_y)
