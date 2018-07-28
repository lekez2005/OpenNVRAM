import contact
import design
import debug
from tech import drc, parameter, spice, info
from ptx import ptx
from vector import vector
from globals import OPTS
import math
from utils import round_to_grid

class pgate(design.design):
    """
    This is a module that implements some shared functions for parameterized gates.
    """

    def __init__(self, name, rail_offset=0.0):
        """ Creates a generic cell """
        design.design.__init__(self, name)
        self.rail_offset = rail_offset

    def determine_tx_mults(self):
        """
        Determines the number of fingers needed to achieve the size within
        the height constraint. This may fail if the user has a tight height.
        """
        # Do a quick sanity check and bail if unlikely feasible height
        # Sanity check. can we make an inverter in the height with minimum tx sizes?
        # Assume we need 3 metal 1 pitches (2 power rails, one between the tx for the drain)
        # plus the tx height
        nmos = ptx(tx_type="nmos")
        pmos = ptx(width=drc["minwidth_tx"], tx_type="pmos")
        tx_height = nmos.height + pmos.height + 2*self.rail_offset
        
        # This is the extra space needed to ensure DRC rules to the active contacts
        extra_contact_space = nmos.height - nmos.tx_width
        total_height = tx_height + self.min_channel
        debug.check(self.height> total_height,"Cell height {0} too small for simple min height {1}.".format(self.height,total_height))

        # Determine the height left to the transistors to determine the number of fingers
        tx_height_available = self.height - self.min_channel - 2*extra_contact_space - 2*self.rail_offset

        # Determine the number of mults for each to fit width into available space
        self.nmos_width = self.nmos_size*drc["minwidth_tx"]
        self.pmos_width = self.pmos_size*drc["minwidth_tx"]
        # Divide the height according to size ratio
        nmos_height_available = self.nmos_width/(self.nmos_width+self.pmos_width) * tx_height_available
        pmos_height_available = self.pmos_width/(self.nmos_width+self.pmos_width) * tx_height_available

        debug.info(2,"Height avail {0} PMOS height {1} NMOS height {2}".format(tx_height_available, nmos_height_available, pmos_height_available))


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
        



    def connect_pin_to_rail(self,inst,pin,supply):
        """ Conencts a ptx pin to a supply rail. """
        source_pin = inst.get_pin(pin)
        supply_pin = self.get_pin(supply)
        if supply_pin.overlaps(source_pin):
            return
            
        if supply=="gnd":
            height=supply_pin.by()-source_pin.by()
        elif supply=="vdd":
            height=supply_pin.uy()-source_pin.by()
        else:
            debug.error("Invalid supply name.",-1)    
        
        if abs(height)>0:
            self.add_rect(layer="metal1",
                          offset=source_pin.ll(),
                          height=height,
                          width=source_pin.width())
    
    def route_input_gate(self, pmos_inst, nmos_inst, ypos, name, position="left", rotate=90):
        """ Route the input gate to the left side of the cell for access.
        Position specifies to place the contact the left, center, or right of gate. """

        nmos_gate_pin = nmos_inst.get_pin("G")
        pmos_gate_pin = pmos_inst.get_pin("G")

        # Check if the gates are aligned and give an error if they aren't!
        debug.check(nmos_gate_pin.ll().x==pmos_gate_pin.ll().x, "Connecting unaligned gates not supported.")
        
        # Pick point on the left of NMOS and connect down to PMOS
        nmos_gate_pos = nmos_gate_pin.ll() + vector(0.5*self.m1_width,0)
        pmos_gate_pos = vector(nmos_gate_pos.x,pmos_gate_pin.bc().y)
        self.add_path("metal1",[nmos_gate_pos,pmos_gate_pos])
        mid_path = vector(nmos_gate_pos.x, ypos)

        

        pin_x_pos = nmos_gate_pin.lx()
        if position=="center":
            pin_x_pos += 0.5*self.m1_width
        elif position=="left":
            pin_x_pos -= self.m1_width
        elif position=="right":
            pin_x_pos += self.m1_width
        else:
            debug.error("Invalid contact placement option.", -1)

        pin_offset = vector(pin_x_pos, ypos)
        
        self.add_layout_pin_center_rect(text=name,
                                            layer="metal1",
                                            offset=pin_offset)
        self.add_path("metal1",[pin_offset, mid_path])

    def extend_wells(self, middle_position):
        """ Extend the n/p wells to cover whole cell """

        # Add a rail width to extend the well to the top of the rail
        max_y_offset = self.height + 0.5*self.rail_height
        self.nwell_position = middle_position
        nwell_height = max_y_offset - middle_position.y
        if info["has_nwell"]:
            self.add_rect(layer="nwell",
                          offset=middle_position,
                          width=self.well_width,
                          height=nwell_height)
        # self.add_rect(layer="vtg",
        #               offset=self.nwell_position,
        #               width=self.well_width,
        #               height=nwell_height)

        # use for cell pr boundary
        pwell_position = vector(0, 0)
        pwell_height = middle_position.y-pwell_position.y
        if info["has_pwell"]:
            self.add_rect(layer="pwell",
                          offset=pwell_position,
                          width=self.well_width,
                          height=self.height)
        # self.add_rect(layer="vtg",
        #               offset=pwell_position,
        #               width=self.well_width,
        #               height=pwell_height)

    def add_nwell_contact(self, pmos, pmos_pos, size=[1, 1]):
        """ Add an nwell contact next to the given pmos device. """
        
        layer_stack = ("cont_active", "contact", "cont_metal1")
        dummy_well_contact = contact.contact(layer_stack=layer_stack, dimensions=size,
                                             implant_type="n", well_type="n") # for calculations
        active_well_enclosure = drc["well_enclosure_active"]
        
        # To the right a spacing away from the pmos right poly dummy
        contact_xoffset = self.well_width - (0.5*dummy_well_contact.first_layer_width + active_well_enclosure)
        contact_yoffset = self.height - (0.5*dummy_well_contact.first_layer_height + active_well_enclosure) - self.rail_offset
        contact_offset = vector(contact_xoffset, contact_yoffset)
        self.nwell_contact=self.add_contact_center(layers=layer_stack,
                                                   offset=contact_offset,
                                                   size = size,
                                                   implant_type="n",
                                                   well_type="n")
        self.add_rect_center(layer="metal1",
                             offset=contact_offset + vector(0,0.5*(self.height-contact_offset.y)),
                             width=self.nwell_contact.mod.second_layer_width,
                             height=self.height - contact_offset.y)
        # add nimplant to fulfill minimum area requirements
        # locate right edge of pmos pimplant
        pimplant_right = pmos_pos.x + (pmos.implant_width - pmos.implant_enclose)
        nimplant_height = pmos.implant_height
        nimplant_right = contact_offset.x + 0.5*dummy_well_contact.first_layer_width + drc["implant_enclosure_active"]
        nimplant_width = nimplant_right - pimplant_right
        self.add_rect(layer="nimplant",
                     offset=vector(pimplant_right, self.height-nimplant_height-self.rail_offset),
                     width=nimplant_width,
                     height=nimplant_height)


    def add_pwell_contact(self, nmos, nmos_pos, size=[1, 1]):
        """ Add an pwell contact next to the given nmos device. """

        layer_stack = ("cont_active", "contact", "cont_metal1")

        dummy_well_contact = contact.contact(layer_stack=layer_stack, dimensions=size,
                                             implant_type="p", well_type="p") # for calculations
        active_well_enclosure = drc["well_enclosure_active"]
        
        # To the right a spacing away from the nmos right active edge
        contact_xoffset = self.well_width - (0.5*dummy_well_contact.first_layer_width + active_well_enclosure)
        # Must be at least an well enclosure of active up from the bottom of the well
        contact_yoffset = 0.5*dummy_well_contact.first_layer_height + active_well_enclosure + self.rail_offset
        contact_offset = vector(contact_xoffset, contact_yoffset)

        self.pwell_contact=self.add_contact_center(layers=layer_stack,
                                                   offset=contact_offset,
                                                   size=size,
                                                   implant_type="p",
                                                   well_type="p")
        self.add_rect_center(layer="metal1",
                             offset=contact_offset.scale(1,0.5),
                             width=self.pwell_contact.mod.second_layer_width,
                             height=contact_offset.y)

        # add pimplant to fulfill minimum area requirements
        # locate right edge of nmos nimplant
        nimplant_right = nmos_pos.x + (nmos.implant_width - nmos.implant_enclose)
        pimplant_height = nmos.implant_height
        pimplant_right = contact_offset.x + 0.5*dummy_well_contact.first_layer_width + drc["implant_enclosure_active"]
        pimplant_width = pimplant_right - nimplant_right
        self.add_rect(layer="pimplant",
                     offset=vector(nimplant_right, self.rail_offset),
                     width=pimplant_width,
                     height=pimplant_height)
