import math
import hierarchy_layout
import hierarchy_spice
import globals
import utils
import verify
import debug
import os
from globals import OPTS
from tech import drc
from tech import layer as tech_layers
from tech import purpose as tech_purpose
from vector import vector


class design(hierarchy_spice.spice, hierarchy_layout.layout):
    """
    Design Class for all modules to inherit the base features.
    Class consisting of a set of modules and instances of these modules
    """
    name_map = []
    

    def __init__(self, name):
        self.gds_file = OPTS.openram_tech + "gds_lib/" + name + ".gds"
        self.sp_file = OPTS.openram_tech + "sp_lib/" + name + ".sp"

        self.name = name
        hierarchy_layout.layout.__init__(self, name)
        hierarchy_spice.spice.__init__(self, name)

        self.setup_drc_constants()
        
        # Check if the name already exists, if so, give an error
        # because each reference must be a unique name.
        # These modules ensure unique names or have no changes if they
        # aren't unique
        ok_list = ['ms_flop.ms_flop',
                   'bitcell.bitcell',
                   'contact.contact',
                   'ptx.ptx',
                   'ptx_spice.ptx_spice',
                   'sram.sram',
                   'hierarchical_predecode2x4.hierarchical_predecode2x4',
                   'hierarchical_predecode3x8.hierarchical_predecode3x8']
        if name not in design.name_map:
            design.name_map.append(name)
        elif str(self.__class__) in ok_list:
            pass
        else:
            debug.error("Duplicate layout reference name {0} of class {1}. GDS2 requires names be unique.".format(name,self.__class__),-1)
        
    def setup_drc_constants(self):
        """ These are some DRC constants used in many places in the compiler."""

        self.well_width = drc["minwidth_well"]
        self.poly_width = drc["minwidth_poly"]
        self.poly_space = drc["poly_to_poly"]
        self.poly_pitch = self.poly_width + self.poly_space
        self.m1_width = drc["minwidth_metal1"]
        self.m1_space = drc["metal1_to_metal1"]        
        self.m2_width = drc["minwidth_metal2"]
        self.m2_space = drc["metal2_to_metal2"]        
        self.m3_width = drc["minwidth_metal3"]
        self.m3_space = drc["metal3_to_metal3"]
        self.m4_width = drc["minwidth_metal4"]
        self.m4_space = drc["metal4_to_metal4"]
        self.active_width = drc["minwidth_active"]
        self.contact_width = drc["minwidth_contact"]
        self.contact_spacing = drc["contact_to_contact"]
        self.rail_height = drc["rail_height"]
        
        self.poly_to_active = drc["poly_to_active"]
        self.poly_extend_active = drc["poly_extend_active"]
        self.contact_to_gate = drc["contact_to_gate"]
        self.well_enclose_active = drc["well_enclosure_active"]
        self.implant_enclose_active = drc["implant_enclosure_active"]
        self.implant_space = drc["implant_to_implant"]

        self.minarea_metal1_contact = drc["minarea_metal1_contact"]

        self.wide_m1_space = drc["metal1_to_metal1_line_end"]
        self.line_end_space = drc["metal1_to_metal1_line_end"]
        self.parallel_line_space = drc["parallel_metal1_to_metal1"]
        self.metal1_minwidth_fill = utils.ceil(drc["minarea_metal1_minwidth"]/self.m1_width)
        self.poly_vert_space = drc["poly_end_to_end"]

    def get_layout_pins(self,inst):
        """ Return a map of pin locations of the instance offset """
        # find the instance
        for i in self.insts:
            if i.name == inst.name:
                break
        else:
            debug.error("Couldn't find instance {0}".format(inst.name),-1)
        inst_map = inst.mod.pin_map
        return inst_map

    def calculate_num_contacts(self, tx_width):
        """
        Calculates the possible number of source/drain contacts in a finger.
        """
        import contact
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

    def get_dummy_poly(self, cell, from_gds=True):
        if "po_dummy" in tech_layers:
            if from_gds:
                rects = cell.gds.getShapesInLayer(tech_layers["po_dummy"], tech_purpose["po_dummy"])
            else:
                filter_match = lambda x: (x.__class__.__name__ == "rectangle" and x.layerNumber == tech_layers["po_dummy"] and
                                   x.layerPurpose == tech_purpose["po_dummy"])
                rects = map(lambda x: x.boundary, filter(filter_match, self.objs))
            leftmost = min(map(lambda x: x[0], map(lambda x: x[0], rects)))
            rightmost = max(map(lambda x: x[0], map(lambda x: x[1], rects)))
            return (leftmost, rightmost)

    def add_dummy_poly(self, cell, instances, words_per_row, from_gds=True):
        leftmost, rightmost = self.get_dummy_poly(cell, from_gds=True)
        if leftmost is not None:
            x_offsets = []
            if words_per_row > 1:
                for inst in instances:
                    x_offsets.append(leftmost - self.poly_pitch + inst.lx())  # left
                    x_offsets.append(inst.rx() + (inst.width - rightmost) + self.poly_pitch) #3 right
            else:
                x_offsets.append(leftmost - self.poly_pitch + instances[0].lx())  # left
                x_offsets.append(instances[-1].rx() + (instances[-1].width - rightmost) + self.poly_pitch)  # 3 right
            inst = instances[0]
            for x_offset in x_offsets:
                self.add_rect("po_dummy", offset=vector(x_offset, inst.by() + 0.5 * self.poly_vert_space),
                              width=self.poly_width,
                              height=inst.height - self.poly_vert_space)



        

    def DRC_LVS(self, final_verification=False):
        """Checks both DRC and LVS for a module"""
        if OPTS.check_lvsdrc:
            tempspice = OPTS.openram_temp + "/temp.sp"
            tempgds = OPTS.openram_temp + "/temp.gds"
            self.sp_write(tempspice)
            self.gds_write(tempgds)
            debug.check(verify.run_drc(self.name, tempgds, exception_group=self.__class__.__name__) == 0,"DRC failed for {0}".format(self.name))
            debug.check(verify.run_lvs(self.name, tempgds, tempspice, final_verification) == 0,"LVS failed for {0}".format(self.name))
            os.remove(tempspice)
            os.remove(tempgds)

    def DRC(self):
        """Checks DRC for a module"""
        if OPTS.check_lvsdrc:
            tempgds = OPTS.openram_temp + "/temp.gds"
            self.gds_write(tempgds)
            debug.check(verify.run_drc(self.name, tempgds, exception_group=self.__class__.__name__) == 0,"DRC failed for {0}".format(self.name))
            os.remove(tempgds)

    def LVS(self, final_verification=False):
        """Checks LVS for a module"""
        if OPTS.check_lvsdrc:
            tempspice = OPTS.openram_temp + "/temp.sp"
            tempgds = OPTS.openram_temp + "/temp.gds"
            self.sp_write(tempspice)
            self.gds_write(tempgds)
            debug.check(verify.run_lvs(self.name, tempgds, tempspice, final_verification) == 0,"LVS failed for {0}".format(self.name))
            os.remove(tempspice)
            os.remove(tempgds)

    def __str__(self):
        """ override print function output """
        return "design: " + self.name

    def __repr__(self):
        """ override print function output """
        text="( design: " + self.name + " pins=" + str(self.pins) + " " + str(self.width) + "x" + str(self.height) + " )\n"
        for i in self.objs:
            text+=str(i)+",\n"
        for i in self.insts:
            text+=str(i)+",\n"
        return text
     
    def analytical_power(self, proc, vdd, temp, load):
        """ Get total power of a module  """
        total_module_power = self.return_power()
        for inst in self.insts:
            total_module_power += inst.mod.analytical_power(proc, vdd, temp, load)
        return total_module_power
