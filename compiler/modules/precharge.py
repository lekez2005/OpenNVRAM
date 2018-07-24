import contact
import pgate
import debug
from tech import drc, parameter
from ptx import ptx
from vector import vector
from globals import OPTS
import utils

class precharge(pgate.pgate):
    """
    Creates a single precharge cell
    This module implements the precharge bitline cell used in the design.
    """

    def __init__(self, name, size=1):
        pgate.pgate.__init__(self, name)
        debug.info(2, "create single precharge cell: {0}".format(name))

        c = reload(__import__(OPTS.bitcell))
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell = self.mod_bitcell()
        
        self.beta = parameter["beta"]
        self.ptx_width = self.beta*parameter["min_tx_size"]
        self.width = self.bitcell.width

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        self.add_pin_list(["bl", "br", "en", "vdd"])

    def create_layout(self):
        self.create_ptx()
        self.add_ptx()
        self.connect_gates()
        self.add_en()
        self.add_nwell_and_contact()
        self.add_vdd_rail()
        self.add_bitlines()
        self.connect_to_bitlines()
        self.join_implants()

    def create_ptx(self):
        """Initializes the upper and lower pmos"""
        # top left pmos
        self.tl_pmos = ptx(tx_type="pmos",
                        width=self.ptx_width,
                        dummy_pos=[0, 1],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.tl_pmos)

        # top right pmos
        self.tr_pmos = ptx(tx_type="pmos",
                        width=self.ptx_width,
                        dummy_pos=[2, 3],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.tl_pmos)

        # bottom pmos
        self.b_pmos = ptx(tx_type="pmos",
                        width=self.ptx_width,
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.b_pmos)

        # Compute the other pmos2 location, but determining offset to overlap the
        # source and drain pins
        self.overlap_offset = self.tl_pmos.get_pin("D").ll() - self.tl_pmos.get_pin("S").ll()
        


    def add_vdd_rail(self):
        """Adds a vdd rail at the top of the cell"""
        # adds the rail across the width of the cell
        vdd_position = vector(0, self.height - self.rail_height)
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=vdd_position,
                            width=self.width,
                            height = self.rail_height)

        self.connect_pin_to_rail(self.upper_pmos2_inst,"S","vdd")

    def rect_to_pin(self, rect, offset=vector(0, 0), mirror="", rotate=0):
        """ convert rectangle to pin. This is useful for calculating rectangle
        offsets after translation, mirroring or rotation. Users pin_layout
        class's transform method """
        import pin_layout
        boundary = [rect.offset, [rect.offset.x+rect.width, rect.offset.y+rect.height]]
        dummy_pin = pin_layout.pin_layout("X", boundary, "metal1")
        dummy_pin.transform(offset=offset, mirror=mirror,rotate=rotate)
        return dummy_pin
        
    def add_ptx(self):
        """Adds both the upper_pmos and lower_pmos to the module"""
        # adds the lower pmos to layout

        # mirror the bottom pmos across the x-axis
        bottom_mirror = "MX"

                # the base of the cell will be determined by the implant of the bottom
        # transistor
        implant_rect = self.rect_to_pin(self.b_pmos.implant_rect, mirror=bottom_mirror)

        # x offset should be first dummy poly to active
        x_offset = 2*self.b_pmos.poly_pitch - self.b_pmos.end_to_poly
        y_offset = -implant_rect.by()

        self.lower_pmos_position = vector(x_offset, y_offset)
        self.lower_pmos_inst=self.add_inst(name="lower_pmos",
                                           mirror=bottom_mirror,
                                           mod=self.b_pmos,
                                           offset=self.lower_pmos_position)
        self.connect_inst(["bl", "en", "br", "vdd"])

        # the implants of bottom and top pmoses should be separated by
        # self.implant_space
        self.lower_tx_implant = self.rect_to_pin(self.b_pmos.implant_rect,
            offset=self.lower_pmos_position, mirror=bottom_mirror)
        self.implant_space = 2.5*self.m1_space

        self.tl_implant_by = self.lower_tx_implant.by() + self.lower_tx_implant.height() + self.implant_space
        before_offset = self.rect_to_pin(self.tl_pmos.implant_rect).by()
        topleft_y_offset = self.tl_implant_by - before_offset

       

        # adds the upper pmos(s) to layout
        self.upper_pmos1_pos = vector(self.lower_pmos_position.x, topleft_y_offset)
        self.upper_pmos1_inst=self.add_inst(name="upper_pmos1",
                                            mod=self.tl_pmos,
                                            offset=self.upper_pmos1_pos)
        self.connect_inst(["bl", "en", "vdd", "vdd"])

        upper_pmos2_pos = self.upper_pmos1_pos + self.overlap_offset
        self.upper_pmos2_inst=self.add_inst(name="upper_pmos2",
                                            mod=self.tr_pmos,
                                            offset=upper_pmos2_pos)
        self.connect_inst(["br", "en", "vdd", "vdd"])

        self.height = self.upper_pmos1_pos.y + self.tl_pmos.height + self.m1_space

    def connect_gates(self):
        """Connects the upper and lower pmos together"""

        offset = self.lower_pmos_inst.get_pin("G").ll()
        # connects the top and bottom pmos' gates together
        ylength = self.upper_pmos1_inst.get_pin("G").ll().y - offset.y
        self.add_rect(layer="metal1",
                      offset=offset,
                      width=self.m1_width,
                      height=ylength)

        # connects the two poly for the two upper pmos(s)
        left_gate = self.upper_pmos1_inst.get_pin("G").center().x
        right_gate = self.upper_pmos2_inst.get_pin("G").center().x
        xlength = right_gate - left_gate
        rect_offset = vector(0.5*(left_gate + right_gate), self.upper_pmos1_inst.get_pin("G").center().y)
        self.add_rect_center(layer="metal1",
                      offset=rect_offset,
                      width=xlength,
                      height=self.m1_width)

    def add_en(self):
        """Adds the en input rail, en contact/vias, and connects to the pmos"""
        # adds the en contact to connect the gates to the en rail on metal1
        offset = self.lower_pmos_inst.get_pin("G").ul() + vector(0,0.5*self.m1_space)

        # adds the en rail on metal1
        self.add_layout_pin_center_segment(text="en",
                                           layer="metal1",
                                           start=offset.scale(0,1),
                                           end=offset.scale(0,1)+vector(self.width,0))

                     
    def add_nwell_and_contact(self):
        """Adds a nwell tap to connect to the vdd rail
        the contact is positioned to align with the top right cornell of the
        cell """
        layer_stack = ("cont_active", "contact", "cont_metal1")
        dummy_well_contact = contact.contact(layer_stack=layer_stack, dimensions=[1, 6],
                                             implant_type="n", well_type="n")
        active_well_enclosure = drc["well_enclosure_active"]
        x_offset = self.width - (0.5*dummy_well_contact.first_layer_width + active_well_enclosure)
        y_offset = self.height - (0.5*dummy_well_contact.first_layer_height + active_well_enclosure)
        self.add_contact_center(layers=layer_stack,
                                size=[1, 6],
                                offset=vector(x_offset, y_offset),
                                implant_type="n",
                                well_type="n")

        self.add_rect(layer="nwell",
                      offset=vector(0,0),
                      width=self.width,
                      height=self.height)


    def add_bitlines(self):
        """Adds both bit-line and bit-line-bar to the module"""
        # adds the BL on metal 2
        offset = vector(self.bitcell.get_pin("BL").cx(),0) - vector(0.5 * self.m2_width,0)
        self.add_layout_pin(text="bl",
                            layer="metal2",
                            offset=offset,
                            width=drc['minwidth_metal2'],
                            height=self.height)

        # adds the BR on metal 2
        offset = vector(self.bitcell.get_pin("BR").cx(),0) - vector(0.5 * self.m2_width,0)
        self.add_layout_pin(text="br",
                            layer="metal2",
                            offset=offset,
                            width=drc['minwidth_metal2'],
                            height=self.height)

    def connect_to_bitlines(self):
        self.add_bitline_contacts()
        self.connect_pmos(self.lower_pmos_inst.get_pin("S"),self.get_pin("bl"), "left")
        self.connect_pmos(self.lower_pmos_inst.get_pin("D"),self.get_pin("br"), "right")
        self.connect_pmos(self.upper_pmos1_inst.get_pin("S"),self.get_pin("bl"), "left")
        self.connect_pmos(self.upper_pmos2_inst.get_pin("D"),self.get_pin("br"), "right")
        

    def add_bitline_contacts(self):
        """Adds contacts/via from metal1 to metal2 for bit-lines"""

        stack=("metal1", "via1", "metal2")

        # metal 1 fill if minimum m1 area drc not met
        active_m1_height = max(self.lower_pmos_inst.get_pin("S").height(), contact.m1m2.first_layer_height)
        active_m1_width = self.lower_pmos_inst.get_pin("S").width()
        metal1_contact_area = active_m1_height*active_m1_width
        min_m1_area = drc["minarea_metal1_contact"]

        if metal1_contact_area < min_m1_area:
            fill_width = utils.ceil(min_m1_area/active_m1_height)
            self.expand_pin_m1(self.lower_pmos_inst.get_pin("S"), fill_width,
                               active_m1_height, "left")
            self.expand_pin_m1(self.upper_pmos1_inst.get_pin("S"), fill_width,
                               active_m1_height, "left")
            self.expand_pin_m1(self.lower_pmos_inst.get_pin("D"), fill_width,
                               active_m1_height, "right")
            self.expand_pin_m1(self.upper_pmos2_inst.get_pin("D"), fill_width,
                               active_m1_height, "right")

        pos = self.lower_pmos_inst.get_pin("S").center()
        self.add_contact_center(layers=stack,
                                offset=pos)
        pos = self.lower_pmos_inst.get_pin("D").center()
        self.add_contact_center(layers=stack,
                                offset=pos)
        pos = self.upper_pmos1_inst.get_pin("S").center()
        self.add_contact_center(layers=stack,
                                offset=pos)
        pos = self.upper_pmos2_inst.get_pin("D").center()
        self.add_contact_center(layers=stack,
                                offset=pos)

    def expand_pin_m1(self, pin, width, height, direction):
        y_offset = pin.center().y
        if direction == "left":
            x_offset = pin.center().x - 0.5*(width-pin.width())
        else:
            x_offset = pin.center().x + 0.5*(width-pin.width())
        self.add_rect_center(layer="metal1",
                             offset=vector(x_offset, y_offset),
                             width=width,
                             height=height)

    def connect_pmos(self, pmos_pin, bit_pin, direction):
        """ Connect pmos pin to bitline pin """

        left_pos = min(pmos_pin.center().x, bit_pin.center().x)
        right_pos = max(pmos_pin.center().x, bit_pin.center().x)
        via_enclosure = 0.75*self.m2_space # wide via metals mimimum enclosure
        if direction == "left":
            x_offset = left_pos 
        else:
            x_offset = left_pos - via_enclosure
        width = right_pos - left_pos + via_enclosure

        height = contact.m1m2.second_layer_height
        y_offset = pmos_pin.center().y - 0.5*height

        self.add_rect(layer="metal2",
                      offset=vector(x_offset, y_offset),
                      width=width,
                      height=height)

    def join_implants(self):
        """ Draw implant between top transistors and bottom transistors implants
        to bypass minimum drc implant spacing rules"""
        lower_implant_top = self.lower_pmos_inst.get_pin("D").uy()
        upper_implant_bottom = self.tl_pmos.implant_rect.by()
        height = upper_implant_bottom - lower_implant_top
        width = self.b_pmos.implant_width
        self.add_rect(layer="pimplant",
                            offset = self.lower_tx_implant.ul(),
                            width=width,
                            height=self.implant_space)

        
