import design
import debug
from tech import drc
from tech import layer as tech_layers
from vector import vector
import contact
from ptx_spice import ptx_spice
from globals import OPTS


class single_level_column_mux(design.design):
    """
    This module implements the columnmux bitline cell used in the design.
    Creates a single columnmux cell.
    """

    def __init__(self, tx_size):
        name="single_level_column_mux_{}".format(tx_size)
        design.design.__init__(self, name)
        debug.info(2, "create single column mux cell: {0}".format(name))

        c = reload(__import__(OPTS.bitcell))
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell = self.mod_bitcell()
        
        self.ptx_width = tx_size * drc["minwidth_tx"]
        self.tx_mults = 2
        self.add_pin_list(["bl", "br", "bl_out", "br_out", "sel", "gnd"])
        self.create_layout()

    def create_layout(self):

        self.width = self.bitcell.width
        self.add_ptx()

        self.connect_gates()
        self.add_bitline_pins()


    def add_ptx(self):
        """ Create the two pass gate NMOS transistors to switch the bitlines"""

        gate_contact_height = contact.poly.second_layer_height
        middle_space = gate_contact_height + 2*self.line_end_space
        # TODO tune extra_top_space. This value was selected to pass drc
        extra_top_space = drc["metal1_to_metal1_wide2"]
        top_space = self.poly_extend_active + drc["ptx_implant_enclosure_active"] + extra_top_space

        extra_bottom_space = 0.5*self.m2_space# to give room for sel pin
        bottom_space = top_space + extra_bottom_space

        self.height = top_space + bottom_space + middle_space + 2*self.ptx_width
        self.poly_height = middle_space + 2*(self.ptx_width + self.poly_extend_active)
        self.mid_y = bottom_space + 0.5*middle_space + self.ptx_width
        self.mid_x = 0.5 * self.width

        # add active
        active_enclose_contact = drc["active_enclosure_contact"]
        self.poly_pitch = self.poly_width + self.poly_space
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate
        self.active_width = 2 * self.end_to_poly + self.tx_mults * self.poly_pitch - self.poly_space

        self.active_mid_y_top = self.mid_y + 0.5 * (middle_space + self.ptx_width)
        self.active_mid_y_bot = self.mid_y - 0.5 * (middle_space + self.ptx_width)

        self.add_rect_center("active", offset=vector(self.mid_x, self.active_mid_y_top), width=self.active_width,
                             height=self.ptx_width)
        self.add_rect_center("active", offset=vector(self.mid_x, self.active_mid_y_bot), width=self.active_width,
                             height=self.ptx_width)

        # add poly
        real_poly_start = self.mid_x - 0.5*self.active_width + self.end_to_poly
        if "po_dummy" in tech_layers:
            self.no_dummy_poly = 4
            self.poly_x_start = real_poly_start - 2*self.poly_pitch
            poly_layers = 2 * ["po_dummy"] + self.tx_mults * ["poly"] + 2 * ["po_dummy"]
            self.total_poly = self.tx_mults + 4
        else:
            poly_layers = self.tx_mults * ["poly"]
            self.poly_x_start = real_poly_start
            self.total_poly = self.tx_mults

        for i in range(self.total_poly):
            offset = vector(self.poly_x_start + i*self.poly_pitch + 0.5*self.poly_width, self.mid_y)
            self.add_rect_center(poly_layers[i], offset=offset, width=self.poly_width, height=self.poly_height)

        # add implant
        self.add_rect("nimplant", offset=vector(0, 0), width=self.width, height=self.height)

        no_contacts = self.calculate_num_contacts(self.ptx_width)
        self.drain_x = [self.mid_x]
        self.source_x = [self.mid_x - self.poly_pitch, self.mid_x + self.poly_pitch]

        for y_offset in [self.active_mid_y_top, self.active_mid_y_bot]:
            for x_offset in self.drain_x + self.source_x:
                offset = vector(x_offset, y_offset)
                self.add_rect_center("metal1", offset=offset, width=self.m1_width, height=self.ptx_width)
                self.add_contact_center(layers=contact.contact.active_layers, size=[1, no_contacts], offset=offset)
            via_y = y_offset + 0.5*self.ptx_width - 0.5*contact.m1m2.first_layer_height
            self.add_contact_center(layers=contact.contact.m1m2_layers, offset=vector(self.drain_x[0], via_y))
            via_y = y_offset - 0.5*self.ptx_width + 0.5*contact.m1m2.first_layer_height
            for x_offset in self.source_x:
                self.add_contact_center(layers=contact.contact.m1m2_layers, offset=vector(x_offset, via_y))

        
        # Adds nmos1,nmos2 to the module
        self.nmos = ptx_spice(width=self.ptx_width, mults=2, tx_type="nmos")
        self.add_mod(self.nmos)


        self.nmos1=self.add_inst(name="mux_tx1",
                                 mod=self.nmos,
                                 offset=vector(0, 0))
        self.connect_inst(["bl", "sel", "bl_out", "gnd"])

        self.nmos2=self.add_inst(name="mux_tx2",
                                 mod=self.nmos,
                                 offset=vector(0, 0))
        self.connect_inst(["br", "sel", "br_out", "gnd"])


    def connect_gates(self):
        """ Connect the poly gate of the two pass transistors """

        if "po_dummy" in tech_layers:
            poly_x_start = self.poly_x_start + 2*self.poly_pitch
        else:
            poly_x_start = self.poly_x_start
        for i in range(self.tx_mults):
            x_offset = poly_x_start + 0.5*self.poly_width + i*self.poly_pitch
            self.add_contact_center(layers=contact.contact.poly_layers, offset=vector(x_offset, self.mid_y))

        rail_x = self.source_x[0] - 0.5*self.m1_width - self.parallel_line_space - self.m1_width

        gate_right = self.mid_x + 0.5*self.poly_pitch

        self.add_rect("metal1", offset=vector(rail_x, self.mid_y-0.5*self.m1_width), width=gate_right-rail_x)

        via_y = self.active_mid_y_bot - 0.5*self.ptx_width - self.line_end_space - contact.m1m2.first_layer_width
        self.add_rect("metal1", offset=vector(rail_x, via_y), height=self.mid_y-via_y)
        self.add_rect("metal1", offset=vector(rail_x, via_y), width=self.mid_x-rail_x)
        self.add_via(layers=contact.contact.m1m2_layers, offset=vector(self.mid_x, via_y), rotate=90)
        self.add_layout_pin(text="sel", layer="metal2", offset=vector(self.mid_x-0.5*self.m1_width, 0),
                            height=via_y+contact.m1m2.first_layer_width)


    def add_bitline_pins(self):
        """ Add the top and bottom pins to this cell """

        bl_x = self.bitcell.get_pin("BL").lx()
        br_x = self.bitcell.get_pin("BR").lx()

        # bl and bl_out
        via_y = self.active_mid_y_top + 0.5*self.ptx_width - 0.5*contact.m1m2.second_layer_height
        offset = vector(bl_x, via_y)
        self.add_layout_pin(text="bl",
                            layer="metal2",
                            offset=offset,
                            height=self.height-via_y+0.5*self.m2_width)
        self.add_rect("metal2", offset=offset-vector(0, 0.5*self.m2_width), width=self.drain_x[0]-bl_x)

        via_y = self.active_mid_y_top - 0.5 * self.ptx_width + 0.5 * contact.m1m2.second_layer_height
        self.add_layout_pin(text="bl_out",
                            layer="metal2",
                            offset=vector(bl_x, 0),
                            height=via_y)
        self.add_rect("metal2", offset=vector(bl_x, via_y - 0.5 * self.m2_width), width=self.source_x[1] - bl_x)

        # br and br_out
        via_y = self.active_mid_y_bot + 0.5 * self.ptx_width - 0.5 * contact.m1m2.second_layer_height
        offset = vector(br_x, via_y)
        self.add_layout_pin(text="br",
                            layer="metal2",
                            offset=offset,
                            height=self.height - via_y + 0.5*self.m2_width)
        self.add_rect("metal2", offset=vector(self.drain_x[0], via_y-0.5 * self.m2_width),
                      width=br_x - self.drain_x[0] + self.m2_width)

        via_y = self.active_mid_y_bot - 0.5 * self.ptx_width + 0.5 * contact.m1m2.second_layer_height
        self.add_layout_pin(text="br_out",
                            layer="metal2",
                            offset=vector(br_x, 0),
                            height=via_y)
        self.add_rect("metal2", offset=vector(self.source_x[0], via_y - 0.5 * self.m2_width),
                      width=br_x - self.source_x[0]+self.m2_width)