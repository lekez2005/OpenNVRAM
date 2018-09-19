import contact
import design
import debug
from tech import drc, parameter
from tech import layer as tech_layers
from vector import vector
import math
from utils import round_to_grid
import utils

class pgate(design.design):
    """
    This is a module that implements some shared functions for parameterized gates.
    """

    def __init__(self, name, height, size=1, beta=parameter["beta"], contact_pwell=True, contact_nwell=True):
        """ Creates a generic cell """
        design.design.__init__(self, name)
        self.beta = beta
        self.size = size
        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell
        self.height = height


    def determine_tx_mults(self):
        """
        Determines the number of fingers needed to achieve the size within
        the height constraint. This may fail if the user has a tight height.
        """

        self.nmos_size = self.nmos_scale * self.size
        self.pmos_size = self.beta * self.pmos_scale * self.size

        track_extent = self.no_tracks * self.m2_width + (self.no_tracks - 1) * self.m2_space
        gate_contact_height = track_extent + (contact.m1m2.second_layer_height - self.m2_width)
        self.middle_space = gate_contact_height + 2 * self.line_end_space

        min_tx_width = drc["minwidth_tx"]

        min_n_width = self.nmos_scale * min_tx_width
        min_p_width = self.pmos_scale * self.beta * min_tx_width

        rail_extent = 0.5*self.rail_height + self.line_end_space
        self.top_space = max(contact.m1m2.first_layer_height - min_p_width, 0) + rail_extent
        self.bottom_space = max(contact.m1m2.first_layer_height - min_n_width, 0) + rail_extent

        self.well_contact_active_height = contact.active.first_layer_width
        self.well_contact_implant_height = drc["minwidth_implant"]

        active_contact_space = self.poly_extend_active + self.poly_to_active + 0.5*self.well_contact_active_height
        implant_active_space = drc["ptx_implant_enclosure_active"] + 0.5*self.well_contact_implant_height

        self.top_space = max(self.top_space, active_contact_space, implant_active_space)
        self.bottom_space = max(self.bottom_space, active_contact_space, implant_active_space)

        self.tx_height_available = tx_height_available = self.height - (self.top_space +
                                                                        self.middle_space + self.bottom_space)

        debug.check(tx_height_available > min_n_width + min_p_width,
                    "Cell height {0} too small for simple pmos height {1}, nmos height {2}.".format(
                        self.height, min_p_width, min_n_width))


        # Determine the number of mults for each to fit width into available space
        self.nmos_width = self.nmos_size*drc["minwidth_tx"]
        self.pmos_width = self.pmos_size*drc["minwidth_tx"]
        # Divide the height according to size ratio
        nmos_height_available = self.nmos_width/(self.nmos_width+self.pmos_width) * tx_height_available
        pmos_height_available = self.pmos_width/(self.nmos_width+self.pmos_width) * tx_height_available

        debug.info(2,"Height avail {0} PMOS height {1} NMOS height {2}".format(
            tx_height_available, nmos_height_available, pmos_height_available))


        nmos_required_mults = max(int(math.ceil(self.nmos_width/nmos_height_available)),1)
        pmos_required_mults = max(int(math.ceil(self.pmos_width/pmos_height_available)),1)
        # The mults must be the same for easy connection of poly
        self.tx_mults = max(nmos_required_mults, pmos_required_mults)

        # Recompute each mult width and check it isn't too small
        # This could happen if the height is narrow and the size is small
        # User should pick a bigger size to fix it...
        # We also need to round the width to the grid or we will end up with LVS property
        # mismatch errors when fingers are not a grid length and get rounded in the offset geometry.
        self.nmos_width = round_to_grid(self.nmos_width / self.tx_mults)
        debug.check(self.nmos_width>=drc["minwidth_tx"],"Cannot finger NMOS transistors to fit cell height.")
        self.pmos_width = round_to_grid(self.pmos_width / self.tx_mults)
        debug.check(self.pmos_width>=drc["minwidth_tx"],"Cannot finger PMOS transistors to fit cell height.")

    def setup_layout_constants(self):

        self.minarea_metal1_contact = drc["minarea_metal1_contact"]
        self.minside_metal1_contact = drc["minside_metal1_contact"]

        self.contact_pitch = 2 * self.contact_to_gate + self.contact_width + self.poly_width
        self.contact_space = self.contact_pitch - self.contact_width

        non_active_height = self.height - (self.nmos_width + self.pmos_width)
        self.mid_y = round_to_grid(self.nmos_width + 0.5 * non_active_height)

        active_enclose_contact = drc["active_enclosure_contact"]
        self.poly_pitch = self.poly_width + self.poly_space
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate

        self.active_width = 2 * self.end_to_poly + self.tx_mults * self.poly_pitch - self.poly_space
        self.active_mid_y_pmos = self.mid_y + 0.5 * (self.middle_space + self.pmos_width)
        self.active_mid_y_nmos = self.mid_y - 0.5 * (self.middle_space + self.nmos_width)

        implant_enclosure = drc["ptx_implant_enclosure_active"]

        if "po_dummy" in tech_layers:
            self.no_dummy_poly = 4
            self.total_poly = self.tx_mults + self.no_dummy_poly
            poly_extent = self.total_poly * self.poly_pitch - self.poly_space
            self.width = poly_extent - self.poly_width
            self.mid_x = self.width / 2
            self.implant_width = self.width + 2*implant_enclosure
            self.poly_x_start = 0.0
        else:
            self.no_dummy_poly = 0
            self.total_poly = self.tx_mults + self.no_dummy_poly
            self.implant_width = self.width = self.active_width + 2*implant_enclosure
            self.mid_x = self.width / 2
            self.poly_x_start = self.mid_x - 0.5*self.active_width + self.end_to_poly


        self.poly_height = self.middle_space + self.nmos_width + self.pmos_width + 2 * self.poly_extend_active

        self.calulate_body_contacts()
        self.implant_width = max(self.implant_width,
                                 utils.ceil(self.well_contact_active_width + 2*implant_enclosure),
                                 utils.ceil(drc["minarea_implant"]/self.well_contact_implant_height))

        self.nimplant_height = self.mid_y - 0.5*self.well_contact_implant_height
        self.pimplant_height = self.height - 0.5*self.well_contact_implant_height - self.mid_y

        self.nwell_height = self.height - self.mid_y + 0.5*self.well_contact_active_height + implant_enclosure

        self.pmos_contacts = self.calculate_num_contacts(self.pmos_width)
        self.nmos_contacts = self.calculate_num_contacts(self.nmos_width)
        self.active_contact_layers = ("active", "contact", "metal1")

    def calulate_body_contacts(self):
        if self.tx_mults % 2 == 0:
            no_contacts = self.tx_mults + 1
        else:
            no_contacts = self.tx_mults
        self.no_body_contacts = no_contacts = max(3, no_contacts)
        contact_extent = no_contacts*self.contact_pitch - self.contact_space
        self.contact_x_start = self.mid_x - 0.5*contact_extent + 0.5*self.contact_width

        min_area_threshold = drc["minarea_cont_active_threshold"]
        unused_space = self.tx_height_available - (self.pmos_width + self.nmos_width)
        if unused_space + self.well_contact_active_height > min_area_threshold:
            self.well_contact_active_height = utils.ceil(min_area_threshold)
            min_active_width = utils.ceil(drc["minarea_cont_active"] / self.well_contact_active_height)
        else:
            min_active_width = utils.ceil(drc["minarea_cont_active_thin"]/self.well_contact_active_height)
        active_width = max(2*contact.active.first_layer_vertical_enclosure + contact_extent,
                           min_active_width)

        # prevent minimum spacing drc
        if self.width - active_width < drc["active_to_active"]:
            active_width = max(active_width, self.width)
        self.well_contact_active_width =active_width



    def add_poly(self):
        poly_offsets = []
        half_dummy = int(0.5*self.no_dummy_poly)
        poly_layers = half_dummy * ["po_dummy"] + self.tx_mults * ["poly"] +half_dummy * ["po_dummy"]
        for i in range(len(poly_layers)):
            mid_offset = vector(self.poly_x_start + i*self.poly_pitch, self.mid_y)
            poly_offsets.append(mid_offset)
            offset = mid_offset - vector(0.5*self.poly_width,
                                         0.5*self.middle_space + self. nmos_width + self.poly_extend_active)
            self.add_rect(poly_layers[i], offset=offset, width=self.poly_width,
                                 height=self.poly_height)
        if half_dummy > 0:
            self.poly_offsets = poly_offsets[half_dummy: -half_dummy]
        else:
            self.poly_offsets = poly_offsets

    def add_active(self):
        heights = [self.pmos_width, self.nmos_width]
        active_mid_y_pmos = self.mid_y + 0.5 * (self.middle_space + self.pmos_width)
        active_mid_y_nmos = self.mid_y - 0.5 * (self.middle_space + self.nmos_width)
        active_y_offsets = [active_mid_y_pmos, active_mid_y_nmos]
        for i in range(2):
            offset = vector(self.mid_x, active_y_offsets[i])
            self.add_rect_center("active", offset=offset, width=self.active_width, height=heights[i])

    def calculate_source_drain_pos(self):
        contact_x_start = self.mid_x - 0.5*self.active_width + drc["active_enclosure_contact"] + 0.5*self.contact_width
        self.source_positions = [contact_x_start]
        self.drain_positions = []
        for i in range(self.tx_mults):
            x_offset = contact_x_start + (i + 1) * self.contact_pitch
            if i % 2 == 0:
                self.drain_positions.append(x_offset)
            else:
                self.source_positions.append(x_offset)

    def connect_to_vdd(self, positions):
        bottom_pmos = self.mid_y + 0.5*self.middle_space
        for i in range(len(positions)):
            offset = vector(positions[i] - 0.5*self.m1_width, bottom_pmos)
            self.add_rect("metal1", offset=offset, height=self.height - bottom_pmos)
            offset = vector(positions[i], self.active_mid_y_pmos)
            self.add_contact_center(layers=self.active_contact_layers, offset=offset,
                                    size=(1, self.pmos_contacts))

    def connect_to_gnd(self, positions):
        top_nmos = self.mid_y - 0.5*self.middle_space
        for i in range(len(positions)):
            offset = vector(positions[i] - 0.5*self.m1_width, 0)
            self.add_rect("metal1", offset=offset, height=top_nmos)
            offset = vector(positions[i], self.active_mid_y_nmos)
            self.add_contact_center(layers=self.active_contact_layers, offset=offset,
                                    size=(1, self.nmos_contacts))

    def connect_positions_m2(self, positions, mid_y, tx_width, no_contacts, contact_shift):
        m1m2_layers = ("metal1", "via1", "metal2")
        for i in range(len(positions)):
            x_offset = positions[i]
            offset = vector(x_offset, mid_y)
            active_cont = self.add_contact_center(layers=self.active_contact_layers, offset=offset,
                                    size=(1, no_contacts))
            self.add_contact_center(layers=m1m2_layers, offset=offset,
                                    size=(1, max(1, no_contacts-1)))
            if active_cont.mod.first_layer_height < drc["minarea_metal1_minwidth"]/active_cont.mod.first_layer_width:

                if tx_width > drc["parallel_threshold"]:
                    m1_space = drc["parallel_metal1_to_metal1"]
                else:
                    m1_space = self.m1_space
                metal_fill_width = round_to_grid(2*(self.poly_pitch - 0.5*self.m1_width - m1_space))
                height = utils.ceil(max(self.minarea_metal1_contact/metal_fill_width,
                                           active_cont.mod.first_layer_height))
                self.add_rect_center("metal1", offset=offset, height=height,
                                     width=metal_fill_width)
        max_sd_x = max(self.drain_positions + self.source_positions)
        max_metal_fill_width = 2 * (self.poly_pitch - 0.5 * self.m1_width - self.m1_space)
        output_x = self.output_x = max_sd_x + 0.5 * max_metal_fill_width + self.m1_space

        min_drain_x = min(positions)
        offset = vector(positions[0], mid_y - 0.5 * self.m2_width)
        self.add_rect("metal2", offset=offset, width=output_x - min_drain_x)
        offset = vector(output_x, mid_y + contact_shift)
        self.add_contact(layers=m1m2_layers, offset=offset)
        return output_x

    def connect_s_or_d(self, pmos_positions, nmos_positions):

        self.connect_positions_m2(positions=pmos_positions, mid_y=self.active_mid_y_pmos, tx_width=self.pmos_width,
                                  no_contacts=self.pmos_contacts,
                                  contact_shift=0.5*self.m2_width - contact.m1m2.second_layer_height)
        output_x = self.connect_positions_m2(positions=nmos_positions, mid_y=self.active_mid_y_nmos, tx_width=self.nmos_width,
                                  no_contacts=self.nmos_contacts,
                                  contact_shift=-0.5*self.m2_width)

        offset = vector(output_x, self.active_mid_y_nmos)
        self.add_rect("metal1", offset=offset, height=self.active_mid_y_pmos - self.active_mid_y_nmos)


    def add_poly_contacts(self, pin_names, y_shifts):
        fill_height = (self.middle_space - 2 * self.line_end_space)
        min_width = utils.ceil(self.minarea_metal1_contact / fill_height)
        fill_width = max(contact.poly.second_layer_width, min_width)
        for i in range(len(self.poly_offsets)):
            x_offset = self.poly_offsets[i].x
            offset = vector(x_offset, self.mid_y)
            self.add_rect_center("metal1", offset=offset, width=fill_width, height=fill_height)

            offset = vector(x_offset, self.mid_y + y_shifts[i])
            self.add_contact_center(layers=("poly", "contact", "metal1"), offset=offset)
            self.add_layout_pin_center_rect(pin_names[i], "metal1", offset)


    def add_implants(self):
        implant_x = 0.5*(self.width - self.implant_width)
        self.add_rect("nimplant", offset=vector(implant_x, 0.5*self.well_contact_implant_height),
                      width=self.implant_width, height=self.nimplant_height)
        self.add_rect("pimplant", offset=vector(implant_x, self.mid_y), width=self.implant_width,
                      height=self.pimplant_height)
        self.add_rect("nwell", offset=vector(implant_x, self.mid_y), width=self.implant_width, height=self.nwell_height)

    def add_body_contacts(self):

        y_offsets = []
        implants = []
        pin_names = []

        if self.contact_pwell:
            y_offsets.append(0)
            implants.append("pimplant")
            pin_names.append("gnd")
        if self.contact_nwell:
            y_offsets.append(self.height)
            implants.append("nimplant")
            pin_names.append("vdd")

        for i in range(len(y_offsets)):
            y_offset = y_offsets[i]
            self.add_layout_pin_center_rect(pin_names[i], "metal1", offset=vector(self.mid_x, y_offset),
                                            width=self.width, height=self.rail_height)
            self.add_rect_center("active", offset=vector(self.mid_x, y_offset), width=self.well_contact_active_width,
                                 height=self.well_contact_active_height)
            self.add_rect_center(implants[i], offset=vector(self.mid_x, y_offset), width=self.implant_width,
                                 height=self.well_contact_implant_height)
            for j in range(self.no_body_contacts):
                x_offset = self.contact_x_start + j*self.contact_pitch
                self.add_rect_center("contact", offset=vector(x_offset, y_offset))

    def add_output_pin(self):
        self.output_y = (self.active_mid_y_pmos + self.active_mid_y_nmos) / 2
        offset = vector(self.output_x + 0.5 * self.m1_width, self.output_y)
        self.add_layout_pin_center_rect("Z", "metal1", offset=offset)




    def calculate_num_contacts(self, tx_width):
        """
        Calculates the possible number of source/drain contacts in a finger.
        """
        import math
        num_contacts = int(math.ceil(tx_width/(self.contact_width + self.contact_spacing)))
        while num_contacts > 1:
            contact_array = contact.contact(layer_stack=("active", "contact", "metal1"),
                              dimensions=[1, num_contacts],
                              implant_type=None,
                              well_type=None)
            if contact_array.first_layer_height < tx_width and contact_array.second_layer_height < tx_width:
                break
            num_contacts -= 1
        return num_contacts
