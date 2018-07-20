import design
import debug
from tech import drc, info, spice
from tech import layer as tech_layers
from vector import vector
from contact import contact
from contact import poly as poly_contact
from contact import m1m2
import math
import path
import re
import utils

class ptx(design.design):
    """
    This module generates gds and spice of a parametrically NMOS or
    PMOS sized transistor.  Pins are accessed as D, G, S, B.  Width is
    the transistor width. Mults is the number of transistors of the
    given width. Total width is therefore mults*width.  Options allow
    you to connect the fingered gates and active for parallel devices.

    """
    def __init__(self, width=drc["minwidth_tx"], mults=1, tx_type="nmos",
         connect_active=False, connect_poly=False, num_contacts=None, dummy_pos = range(0, 4)):
        # We need to keep unique names because outputting to GDSII
        # will use the last record with a given name. I.e., you will
        # over-write a design in GDS if one has and the other doesn't
        # have poly connected, for example.
        name = "{0}_m{1}_w{2}".format(tx_type, mults, width)
        if connect_active:
            name += "_a"
        if connect_poly:
            name += "_p"
        if num_contacts:
            name += "_c{}".format(num_contacts)
        # replace periods with underscore for newer spice compatibility
        name=re.sub('\.','_',name)

        design.design.__init__(self, name)
        debug.info(3, "create ptx2 structure {0}".format(name))

        self.tx_type = tx_type
        self.mults = mults
        self.tx_width = width
        self.connect_active = connect_active
        self.connect_poly = connect_poly
        self.num_contacts = num_contacts
        self.dummy_pos = dummy_pos

        self.create_spice()
        self.create_layout()

        self.translate_all(self.active_offset)

        # for run-time, we won't check every transitor DRC independently
        # but this may be uncommented for debug purposes
        #self.DRC()

    def setup_drc_constants(self):
        design.design.setup_drc_constants(self)
        if "ptx_well_enclosure_active" in drc:
            self.well_enclose_active = drc["ptx_well_enclosure_active"]
    
    def create_layout(self):
        """Calls all functions related to the generation of the layout"""
        self.setup_layout_constants()
        self.add_active()
        self.add_well_implant()  
        self.add_poly()
        self.add_active_contacts()

    def create_spice(self):
        self.add_pin_list(["D", "G", "S", "B"])
        
        # self.spice.append("\n.SUBCKT {0} {1}".format(self.name,
        #                                              " ".join(self.pins)))
        # Just make a guess since these will actually be decided in the layout later.
        area_sd = 2.5*drc["minwidth_poly"]*self.tx_width
        perimeter_sd = 2*drc["minwidth_poly"] + 2*self.tx_width
        self.spice_device="M{{0}} {{1}} {0} m={1} w={2}u l={3}u pd={4}u ps={4}u as={5}p ad={5}p".format(spice[self.tx_type],
                                                                                                    self.mults,
                                                                                                    self.tx_width,
                                                                                                    drc["minwidth_poly"],
                                                                                                    perimeter_sd,
                                                                                                    area_sd)
        self.spice.append("\n* ptx " + self.spice_device)
        # self.spice.append(".ENDS {0}".format(self.name))

    def setup_layout_constants(self):
        """
        Pre-compute some handy layout parameters.
        """

        if self.num_contacts==None:
            self.num_contacts=self.calculate_num_contacts()

        # Determine layer types needed
        if self.tx_type == "nmos":
            self.implant_type = "n"
            self.well_type = "p"
        elif self.tx_type == "pmos":
            self.implant_type = "p"
            self.well_type = "n"
        else:
            self.error("Invalid transitor type.",-1)
            
            
        # This is not actually instantiated but used for calculations
        self.active_contact = contact(layer_stack=("active", "contact", "metal1"),
                                      dimensions=(1, self.num_contacts))

        
        # The contacted poly pitch (or uncontacted in an odd technology)
        self.poly_pitch = max(2*self.contact_to_gate + self.contact_width + self.poly_width,
                              self.poly_space)

        # The contacted poly pitch (or uncontacted in an odd technology)
        self.contact_pitch = 2*self.contact_to_gate + self.contact_width + self.poly_width
        
        # The enclosure of an active contact. Not sure about second term.
        active_enclose_contact = max(drc["active_enclosure_contact"],
                                     (self.active_width - self.contact_width)/2)
        # This is the distance from the edge of poly to the contacted end of active
        self.end_to_poly = active_enclose_contact + self.contact_width + self.contact_to_gate
        

        # Active width is determined by enclosure on both ends and contacted pitch,
        # at least one poly and n-1 poly pitches
        self.active_width = 2*self.end_to_poly + self.poly_width + (self.mults - 1)*self.poly_pitch

        # Active height is just the transistor width
        self.active_height = self.tx_width

        if "poly_contact_layer" in info:
            self.poly_contact_layer = info["poly_contact_layer"]
        else:
            self.poly_contact_layer = None
        
        if "metal1_to_metal1_wide" in drc:
            self.wide_m1_space = drc["metal1_to_metal1_wide"]
            if self.tx_width < drc["minwidth_tx"] + 0.01:
                self.wide_m1_space += 0.01
        else:
            self.wide_m1_space = drc["metal1_to_metal1"]
        
        # Poly height must include poly extension over active
        self.poly_offset_y = self.well_enclose_active + 0.5*self.active_height
        self.additional_poly = 0.0
        self.poly_height = self.tx_width + 2*self.poly_extend_active
        if self.poly_contact_layer == "metal1":
            self.active_to_contact_center = self.wide_m1_space + poly_contact.second_layer_height*0.5
            poly_height = self.poly_extend_active + self.tx_width + self.active_to_contact_center + \
                0.5*poly_contact.first_layer_height
            self.additional_poly = poly_height - self.poly_height  # additional poly from adding poly_to_m1 via
            self.poly_height = poly_height
            if self.tx_type == "nmos":
                self.poly_offset_y += 0.5*self.additional_poly
                self.poly_contact_center = self.well_enclose_active + self.active_height + self.active_to_contact_center
            else:
                self.poly_offset_y -= 0.5*self.additional_poly
                self.poly_contact_center = self.well_enclose_active - self.active_to_contact_center

        # The active offset is due to the well extension
        self.active_offset = vector([self.well_enclose_active]*2)

        # Well enclosure of active, ensure minwidth as well
        if "ptx_implant_enclosure_active" in drc and drc["ptx_implant_enclosure_active"] > 0:
            self.implant_enclose = drc["ptx_implant_enclosure_active"]
            self.implant_height = self.poly_height + 2*self.implant_enclose
            self.implant_offset = self.active_offset - [self.implant_enclose, self.implant_enclose + self.poly_extend_active]
            if self.tx_type == "pmos":
                self.implant_offset.y -= self.additional_poly
            
        else:
            self.implant_enclose = drc["implant_enclosure_active"]
            self.implant_height = self.active_height + 2*self.implant_enclose
            self.implant_offset = self.active_offset - [self.implant_enclose]*2
        self.implant_width = self.active_width + 2*self.implant_enclose
        
        if info["has_{}well".format(self.well_type)]:
            self.cell_well_width = max(self.active_width + 2*self.well_enclose_active,
                                  self.well_width)
            self.cell_well_height = max(self.tx_width + 2*self.well_enclose_active,
                                   self.well_width)
            # We are going to shift the 0,0, so include that in the width and height
            self.height = self.cell_well_height - self.active_offset.y
            self.width = self.cell_well_width - self.active_offset.x
        else:
            # If no well, use the boundary of the active and poly
            self.height = self.poly_height
            self.width = self.active_width

        self.height = self.implant_height
        # poly dummys
        if "po_dummy" in tech_layers:
            self.width = self.poly_pitch*(self.mults+3) + self.poly_width
            self.dummy_height = drc["po_dummy_min_height"]
            if self.active_height > drc["po_dummy_thresh"]:
                self.dummy_height = self.active_height + 2*drc["po_dummy_enc"]
            self.dummy_y_offset = self.well_enclose_active + 0.5*self.active_height
        
        # The active offset is due to the well extension
        self.active_offset = vector([self.well_enclose_active]*2)

        # This is the center of the first active contact offset (centered vertically)
        self.contact_offset = self.active_offset + vector(active_enclose_contact + 0.5*self.contact_width,
                                                          0.5*self.active_height)
                                     
        
        # Min area results are just flagged for now.
        debug.check(self.active_width*self.active_height>=drc["minarea_active"],"Minimum active area violated.")
        # We do not want to increase the poly dimensions to fix an area problem as it would cause an LVS issue.
        debug.check(self.poly_width*self.poly_height>=drc["minarea_poly"],"Minimum poly area violated.")

    def connect_fingered_poly(self, poly_positions):
        """
        Connect together the poly gates and create the single gate pin.
        The poly positions are the center of the poly gates
        and we will add a single horizontal connection.
        """
        # Nothing to do if there's one poly gate
        if len(poly_positions)<2:
            return
        
        # Remove the old pin and add the new one
        self.remove_layout_pin("G") # only keep the main pin

        # The width of the poly is from the left-most to right-most poly gate
        poly_width = poly_positions[-1].x - poly_positions[0].x + self.poly_width

        if self.poly_contact_layer == "metal1":
            self.add_layout_pin(text="G",
                            layer="metal1",
                            offset=vector(poly_positions[0].x, self.poly_contact_center)-[0.5*self.m1_width]*2,
                            width=poly_width,
                            height=self.m1_width)
        else:
            if self.tx_type == "pmos":
                # This can be limited by poly to active spacing or the poly extension
                distance_below_active = self.poly_width + max(self.poly_to_active,0.5*self.poly_height)
                poly_offset = poly_positions[0] - vector(0.5*self.poly_width, distance_below_active)
            else:
                # This can be limited by poly to active spacing or the poly extension
                distance_above_active = max(self.poly_to_active,0.5*self.poly_height)            
                poly_offset = poly_positions[0] + vector(-0.5*self.poly_width, distance_above_active)
            
            self.add_layout_pin(text="G",
                                layer="poly",
                                offset=poly_offset,
                                width=poly_width,
                                height=drc["minwidth_poly"])


    def connect_fingered_active(self, drain_positions, source_positions):
        """
        Connect each contact  up/down to a source or drain pin
        """
        
        # This is the distance that we must route up or down from the center
        # of the contacts to avoid DRC violations to the other contacts
        pin_offset = vector(0, 0.5*self.active_contact.second_layer_height \
                            + self.wide_m1_space + 0.5*self.m1_width)
        # This is the width of a m1 extend the ends of the pin
        end_offset = vector(self.m1_width/2,0)

        # drains always go to the MIDDLE of the cell, so top of NMOS, bottom of PMOS
        # so reverse the directions for NMOS compared to PMOS.
        if self.tx_type == "pmos":
            drain_dir = -1
            source_dir = 1
        else:
            drain_dir = 1
            source_dir = -1
        source_offset = pin_offset.scale(source_dir,source_dir)    
        self.remove_layout_pin("D") # remove the individual connections
        if self.poly_contact_layer == "metal1":
            self.metal2_width = drc["minwidth_metal2"]
            self.minarea_metal1_contact = drc["minarea_metal1_contact"]
            self.minside_metal1_contact = drc["minside_metal1_contact"]
            metal1_contact_area = self.active_contact.second_layer_height*self.active_contact.second_layer_width

            rect_height = None
            rect_width = None
            metal1_area_fill = None
            max_contact_height = max(self.active_contact.second_layer_height, m1m2.first_layer_height)
            if metal1_contact_area < self.minarea_metal1_contact or \
                ( self.active_contact.second_layer_height < self.minside_metal1_contact and \
                self.active_contact.second_layer_width  < self.minside_metal1_contact ):
                # place metal1 rectangle above the contact. 
                # The top of this metal1 should align with the m1-m2 contact that will be placed when connecting actives together
                rect_height = max(self.minside_metal1_contact, max_contact_height)
                rect_width = max(utils.ceil(self.minarea_metal1_contact/rect_height), self.active_contact.second_layer_width)
            
            for a in drain_positions:
                contact=self.add_contact_center(layers=("metal1", "via1", "metal2"),
                            offset=a,
                            size=(1, 1),
                            implant_type=None,
                            well_type=None)
                # metal2 contact fill for drc
                metal2_fill_height = self.minside_metal1_contact
                metal2_fill_width = utils.ceil(drc["minarea_metal1_contact"]/metal2_fill_height)
                metal2_area_fill = self.add_rect_center(layer="metal2",
                        offset=a,
                        width=metal2_fill_width,
                        height=metal2_fill_height)
                if rect_height is not None:
                    # compute bottom left coordinates
                    rect_x_offset = a.x - 0.5*rect_width
                    rect_y_offset = a.y-0.5*max_contact_height
                    if source_dir == -1:
                        rect_y_offset -= (rect_height-max_contact_height)
                    metal1_area_fill = self.add_rect(layer="metal1",
                        offset=vector(rect_x_offset, rect_y_offset),
                        width=rect_width,
                        height=rect_height)
            if metal1_area_fill is not None:
                distance_from_mid_contact = max(abs(metal1_area_fill.by() - drain_positions[0].y), \
                    abs(metal1_area_fill.uy() - drain_positions[0].y))
                source_offset = vector(pin_offset.x, distance_from_mid_contact + self.wide_m1_space \
                        + 0.5*self.m1_width).scale(source_dir,source_dir)

            drain_pin_width = drain_positions[-1][0]-drain_positions[0][0] + self.metal2_width
            self.add_layout_pin(text="D",
                            layer="metal1",
                            offset=drain_positions[0]-vector(0.5*self.metal2_width, 0.5*self.metal2_width),
                            width=drain_pin_width,
                            height=self.metal2_width)
        else:
            drain_offset = pin_offset.scale(drain_dir,drain_dir)
            # Add each vertical segment
            for a in drain_positions:
                self.add_path(("metal1"), [a,a+drain_offset])
            # Add a single horizontal pin
            self.add_layout_pin_center_segment(text="D",
                                            layer="metal1",
                                            start=drain_positions[0]+drain_offset-end_offset,
                                            end=drain_positions[-1]+drain_offset+end_offset)

        if len(source_positions)>1:
            self.remove_layout_pin("S") # remove the individual connections
            # Add each vertical segment
            for a in source_positions:
                self.add_path(("metal1"), [a,a+source_offset])
            # Add a single horizontal pin
            self.add_layout_pin_center_segment(text="S",
                                               layer="metal1",
                                               start=source_positions[0]+source_offset-end_offset,
                                               end=source_positions[-1]+source_offset+end_offset)

    def add_poly(self):
        """
        Add the poly gates(s) and (optionally) connect them.
        """
        # poly is one contacted spacing from the end and down an extension
        poly_offset = vector(self.active_offset.x + 0.5*self.poly_width + self.end_to_poly,  self.poly_offset_y)

        # poly_positions are the bottom center of the poly gates
        poly_positions = []

        # It is important that these are from left to right, so that the pins are in the right
        # order for the accessors
        for i in range(0, self.mults):
            # Add this duplicate rectangle in case we remove the pin when joining fingers
            self.add_rect_center(layer="poly",
                                 offset=poly_offset,
                                 height=self.poly_height,
                                 width=self.poly_width)
            if self.poly_contact_layer == "metal1":
                contact_pos = vector(poly_offset.x, self.poly_contact_center)
                p_contact=self.add_contact_center(layers=("poly", "contact", "metal1"),
                                            offset=contact_pos,
                                            size=(1, 1),
                                            implant_type=None,
                                            well_type=None)
                self.add_layout_pin_center_rect(text="G",
                                                layer="metal1",
                                                offset=contact_pos,
                                                height=poly_contact.second_layer_height,
                                                width=poly_contact.second_layer_width)
            else:
                self.add_layout_pin_center_rect(text="G",
                                                layer="poly",
                                                offset=poly_offset,
                                                height=self.poly_height,
                                                width=self.poly_width)
            poly_positions.append(poly_offset)
            poly_offset = poly_offset + vector(self.poly_pitch,0)

        # poly dummys
        if "po_dummy" in tech_layers:
            shifts = [-self.mults-2, -self.mults-1, 0, 1]
            for i in self.dummy_pos:
                self.add_rect_center(layer="po_dummy",
                                 offset=vector(poly_offset.x+self.poly_pitch*shifts[i], self.dummy_y_offset),
                                 height=self.dummy_height,
                                 width=self.poly_width)


        if self.connect_poly:
            self.connect_fingered_poly(poly_positions)
            
    def add_active(self):
        """ 
        Adding the diffusion (active region = diffusion region) 
        """
        self.add_rect(layer="active",
                      offset=self.active_offset,
                      width=self.active_width,
                      height=self.active_height)
        

    def add_well_implant(self):
        """
        Add an (optional) well and implant for the type of transistor.
        """
        if info["has_{}well".format(self.well_type)]:                                                                                                                                       
            self.add_rect(layer="{}well".format(self.well_type),
                          offset=(0,0),
                          width=self.cell_well_width,
                          height=self.cell_well_height)
            # If the implant must enclose the active, shift offset
            # and increase width/height
            self.add_rect(layer="{}implant".format(self.implant_type),
                        offset=self.implant_offset,
                        width=self.implant_width,
                        height=self.implant_height)
            if "vtg" in tech_layers:
                self.add_rect(layer="vtg",
                            offset=(0,0),
                            width=self.cell_well_width,
                            height=self.cell_well_height)


    def calculate_num_contacts(self):
        """ 
        Calculates the possible number of source/drain contacts in a finger.
        """
        num_contacts = int(math.ceil(self.tx_width/(self.contact_width + self.contact_spacing)))
        while num_contacts > 1:
            contact_array = contact(layer_stack=("active", "contact", "metal1"),
                              dimensions=[1, num_contacts],
                              implant_type=None,
                              well_type=None)
            if contact_array.first_layer_height < self.tx_width and contact_array.second_layer_height < self.tx_width:
                break
            num_contacts -= 1
        return num_contacts


    def get_contact_positions(self):
        """
        Create a list of the centers of drain and source contact positions.
        """
        # The first one will always be a source
        source_positions = [self.contact_offset]
        drain_positions = []
        # It is important that these are from left to right, so that the pins are in the right
        # order for the accessors.
        for i in range(self.mults):
            if i%2:
                # It's a source... so offset from previous drain.
                source_positions.append(drain_positions[-1] + vector(self.contact_pitch,0))
            else:
                # It's a drain... so offset from previous source.
                drain_positions.append(source_positions[-1] + vector(self.contact_pitch,0))

        return [source_positions,drain_positions]
        
    def add_active_contacts(self):
        """
        Add the active contacts to the transistor.
        """

        [source_positions,drain_positions] = self.get_contact_positions()

        for pos in source_positions:
            contact=self.add_contact_center(layers=("active", "contact", "metal1"),
                                            offset=pos,
                                            size=(1, self.num_contacts),
                                            implant_type=None,
                                            well_type=None)
            self.add_layout_pin_center_rect(text="S",
                                            layer="metal1",
                                            offset=pos,
                                            width=contact.mod.second_layer_width,
                                            height=contact.mod.second_layer_height)

                
        for pos in drain_positions:
            contact=self.add_contact_center(layers=("active", "contact", "metal1"),
                                            offset=pos,
                                            size=(1, self.num_contacts),
                                            implant_type=None,
                                            well_type=None)
            self.add_layout_pin_center_rect(text="D",
                                            layer="metal1",
                                            offset=pos,
                                            width=contact.mod.second_layer_width,
                                            height=contact.mod.second_layer_height)
            
        if self.connect_active:
            self.connect_fingered_active(drain_positions, source_positions)

        
