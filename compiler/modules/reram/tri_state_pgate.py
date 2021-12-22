import tech
from base.contact import well as well_contact, poly as poly_contact, m1m2, cross_poly
from base.design import design, ACTIVE, METAL1, POLY, METAL2
from base.geometry import MIRROR_X_AXIS
from base.vector import vector
from base.well_active_contacts import calculate_num_contacts
from globals import OPTS
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice


class TriStatePgate(design):
    def __init__(self, size=2, name=None):
        name = name or f"tri_state_{size:.4g}"
        self.size = size
        design.__init__(self, name)
        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.setup_layout_constants()
        self.place_modules()
        self.add_ptx_connections()
        self.route_data_input()
        self.route_output_pin()
        self.route_enable_input()
        self.add_power_and_taps()
        self.route_tx_power()
        ptx.flatten_tx_inst(self, self.nmos_inst)
        ptx.flatten_tx_inst(self, self.pmos_inst)
        self.add_boundary()
        tech.add_tech_layers(self)

    def add_pins(self):
        self.add_pin_list("in_bar out en en_bar vdd gnd".split())

    def create_modules(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)

        kwargs = {
            "mults": 4,
            "independent_poly": False,
            "active_cont_pos": [0, 2, 4]
        }

        self.width = self.bitcell.width
        min_width = tech.spice["minwidth_tx"]
        nmos_width = max(min_width, min_width * self.size / 2)
        self.nmos = ptx(width=nmos_width, tx_type="nmos", **kwargs)
        self.add_mod(self.nmos)
        pmos_width = tech.parameter["beta"] * nmos_width
        self.pmos = ptx(width=pmos_width, tx_type="pmos", **kwargs)
        self.add_mod(self.pmos)

        self.nmos_spice = ptx_spice(width=self.nmos.tx_width * 1e6, mults=1,
                                    tx_type="nmos", tx_length=self.nmos.tx_length * 1e6)
        self.add_mod(self.nmos_spice)

        self.pmos_spice = ptx_spice(width=self.pmos.tx_width * 1e6, mults=1,
                                    tx_type="pmos", tx_length=self.pmos.tx_length * 1e6)
        self.add_mod(self.pmos_spice)

    def add_ptx_connections(self):
        nmos_connections = [("gnd", "en", "left_mid_n"),
                            ("left_mid_n", "in_bar", "out"),
                            ("gnd", "en", "right_mid_n"),
                            ("right_mid_n", "in_bar", "out")]
        pmos_connections = [("vdd", "en_bar", "left_mid_p"),
                            ("left_mid_p", "in_bar", "out"),
                            ("vdd", "en_bar", "right_mid_p"),
                            ("right_mid_p", "in_bar", "out")]
        for tx, connections, body in zip([self.nmos_spice, self.pmos_spice],
                                         [nmos_connections, pmos_connections],
                                         ["gnd", "vdd"]):
            for index, connection in enumerate(connections):
                name = f"{tx.tx_type}{index}"
                self.add_inst(name, tx, vector(0, 0))
                self.connect_inst(list(connection) + [body])

    def setup_layout_constants(self):
        well_contact_mid_y = 0.5 * self.rail_height
        well_contact_active_top = well_contact_mid_y + 0.5 * well_contact.first_layer_width
        self.bottom_space = well_contact_active_top + self.get_space(ACTIVE)

        self.nmos_y = self.bottom_space - self.nmos.active_rect.by()

        nmos_active_top = self.nmos_y + self.nmos.active_rect.uy()
        active_to_poly_contact = tech.drc.get("poly_contact_to_n_active",
                                              tech.drc["poly_contact_to_active"])
        self.nmos_poly_cont_y = (nmos_active_top + active_to_poly_contact
                                 + 0.5 * poly_contact.contact_width -
                                 0.5 * poly_contact.first_layer_height)

        nmos_cont_top = self.nmos_poly_cont_y + poly_contact.first_layer_height

        self.pmos_poly_cont_y = nmos_cont_top + self.poly_vert_space
        active_to_poly_contact = tech.drc.get("poly_contact_to_p_active",
                                              tech.drc["poly_contact_to_active"])
        pmos_active_bottom = (self.pmos_poly_cont_y + 0.5 * poly_contact.first_layer_height +
                              0.5 * poly_contact.contact_width +
                              active_to_poly_contact)

        self.pmos_y_top = pmos_active_bottom + (self.pmos.height -
                                                self.pmos.active_rect.by())

        active_to_top = self.pmos.height - self.pmos.active_rect.uy()

        self.height = self.pmos_y_top - active_to_top + self.bottom_space

    def place_modules(self):
        x_offset = 0.5 * self.width - 0.5 * self.nmos.width
        self.nmos_inst = self.add_inst("nmos_layout", mod=self.nmos,
                                       offset=vector(x_offset, self.nmos_y))
        self.connect_inst([], check=False)

        self.pmos_inst = self.add_inst("pmos_layout", mod=self.pmos, mirror=MIRROR_X_AXIS,
                                       offset=vector(x_offset, self.pmos_y_top))
        self.connect_inst([], check=False)

    def route_data_input(self):
        nmos_poly = list(sorted(self.nmos_inst.get_pins("G"), key=lambda x: x.lx()))
        pmos_poly = list(sorted(self.pmos_inst.get_pins("G"), key=lambda x: x.lx()))

        drain_pin = self.pmos_inst.get_pin("D")
        space = max(self.m1_width, m1m2.first_layer_width) + self.get_parallel_space(METAL1)
        poly_right = (nmos_poly[0].rx() + self.poly_vert_space +
                      0.5 * poly_contact.first_layer_width)
        poly_cont_left_m1 = max(drain_pin.lx() - space, poly_right)

        # add poly contact at mid_y
        mid_y = 0.5 * (self.nmos_inst.uy() + self.pmos_inst.by())

        horz_poly = poly_contact.first_layer_width > nmos_poly[0].width()
        for i in [1, 2]:
            # add poly contact
            if horz_poly:
                x_offset = poly_cont_left_m1
            else:
                x_offset = nmos_poly[i].cx()
            self.mid_data_in_x = x_offset

            if horz_poly and i == 1:
                self.add_cross_contact_center(cross_poly, vector(x_offset, mid_y))
            elif not horz_poly:
                self.add_contact_center(poly_contact.layer_stack, vector(x_offset, mid_y))
            # join nmos poly to pmos poly
            self.add_rect(POLY, offset=nmos_poly[i].ul(), width=nmos_poly[i].width(),
                          height=pmos_poly[i].by() - nmos_poly[i].uy())
        # horizontal join poly contact
        layer = POLY if horz_poly else METAL1
        height = (poly_contact.first_layer_height
                  if horz_poly else poly_contact.second_layer_height)
        self.add_rect(layer, vector(x_offset, mid_y - 0.5 * height),
                      height=height, width=nmos_poly[2].cx() - x_offset)

        # poly contact to mid active y

        offset = vector(drain_pin.lx() - space, mid_y - 0.5 * self.m1_width)
        self.add_rect(METAL1, offset, width=x_offset - offset.x)
        y_offset = drain_pin.cy()
        rect = self.add_rect(METAL1, offset, height=y_offset - offset.y)

        # mid active y to top
        self.add_contact_center(m1m2.layer_stack, vector(rect.cx(), y_offset))
        self.add_layout_pin("in_bar", METAL2,
                            vector(rect.cx() - 0.5 * self.m2_width, rect.uy()),
                            height=self.height - rect.uy())

    def route_output_pin(self):
        x_offset = (self.mid_data_in_x + 0.5 * poly_contact.second_layer_height +
                    self.get_line_end_space(METAL1))

        drain_pins = [x.get_pin("D") for x in [self.nmos_inst, self.pmos_inst]]

        for pin_index, pin in enumerate(drain_pins):
            if pin_index == 0:
                y_offset = pin.uy() - self.m1_width
            else:
                y_offset = pin.by()
            self.add_rect(METAL1, vector(pin.lx(), y_offset),
                          width=x_offset + self.m1_width - pin.lx())
        y_offset = drain_pins[0].uy()
        self.add_rect(METAL1, vector(x_offset, y_offset),
                      height=drain_pins[1].by() - y_offset)

        # nmos drain to output
        pin = drain_pins[0]
        self.add_contact_center(m1m2.layer_stack, pin.center())
        self.add_layout_pin("out", METAL2, vector(pin.cx() - 0.5 * self.m2_width, 0),
                            height=pin.cy())

    def route_enable_input(self):
        nmos_poly = list(sorted(self.nmos_inst.get_pins("G"), key=lambda x: x.lx()))
        pmos_poly = list(sorted(self.pmos_inst.get_pins("G"), key=lambda x: x.lx()))
        pin_names = ["en", "en_bar"]

        all_poly = [nmos_poly, pmos_poly]
        all_contact_y = [self.nmos_poly_cont_y, self.pmos_poly_cont_y]

        in_bar_x = (self.get_pin("in_bar").cx() - 0.5 * self.m1_width -
                    self.get_line_end_space(METAL1))

        for inst_index, inst in enumerate([self.nmos_inst, self.pmos_inst]):
            for poly_index in [0, 3]:
                poly_rect = all_poly[inst_index][poly_index]
                if poly_index == 0:
                    x_offset = in_bar_x - 0.5 * (max(poly_contact.second_layer_height,
                                                     m1m2.first_layer_height))
                else:
                    x_offset = poly_rect.lx() + 0.5 * poly_contact.first_layer_width
                y_offset = all_contact_y[inst_index] + 0.5 * poly_contact.first_layer_height

                offset = vector(x_offset, y_offset)

                self.add_cross_contact_center(cross_poly, offset)
                if inst_index == 0:
                    top = y_offset + 0.5 * poly_contact.first_layer_height
                    bottom = poly_rect.uy()
                else:
                    top = poly_rect.by()
                    bottom = y_offset - 0.5 * poly_contact.first_layer_height
                self.add_rect(POLY, vector(poly_rect.lx(), bottom),
                              width=poly_rect.width(), height=top - bottom)

                self.add_contact_center(m1m2.layer_stack, offset, rotate=90)
                self.add_layout_pin(pin_names[inst_index], METAL2,
                                    vector(0, offset.y - 0.5 * self.bus_width),
                                    width=self.width, height=self.bus_width)

    def add_power_and_taps(self):
        pin_names = ["gnd", "vdd"]
        y_offsets = [0, self.height - self.rail_height]
        well_types = ["pwell", "nwell"]
        implant_types = ["p", "n"]
        ptx_insts = [self.nmos_inst, self.pmos_inst]

        max_width = self.width - self.get_space(ACTIVE)
        num_contacts = calculate_num_contacts(self, max_width,
                                              layer_stack=well_contact.layer_stack,
                                              return_sample=False)

        for i in range(2):
            pin = self.add_layout_pin(pin_names[i], METAL1, offset=vector(0, y_offsets[i]),
                                      height=self.rail_height, width=self.width)
            cont = self.add_contact_center(well_contact.layer_stack, pin.center(), rotate=90,
                                           size=[1, num_contacts],
                                           implant_type=implant_types[i],
                                           well_type=well_types[i][0])
            # add well
            well_type = well_types[i]
            if tech.info[f"has_{well_type}"]:
                well_width = cont.mod.first_layer_height + 2 * self.well_enclose_active
                well_width = max(self.width, well_width)
                x_offset = 0.5 * (self.width - well_width)
                ptx_rects = ptx_insts[i].get_layer_shapes(well_type)
                ptx_rect = max(ptx_rects, key=lambda x: x.width * x.height)

                if i == 0:
                    well_top = ptx_rect.uy()
                    well_bottom = min(0, pin.cy() - 0.5 * well_contact.first_layer_width -
                                      self.well_enclose_active)
                else:
                    well_top = max(self.height, pin.cy() +
                                   0.5 * well_contact.first_layer_width +
                                   self.well_enclose_active)
                    well_bottom = ptx_rect.by()
                self.add_rect(well_type, vector(x_offset, well_bottom), width=well_width,
                              height=well_top - well_bottom)

    def route_tx_power(self):
        pin_names = ["gnd", "vdd"]
        insts = [self.nmos_inst, self.pmos_inst]

        for i in range(2):
            power_pin = self.get_pin(pin_names[i])
            for pin in insts[i].get_pins("S"):
                self.add_rect(METAL1, vector(pin.lx(), pin.cy()), width=pin.width(),
                              height=power_pin.cy() - pin.cy())
