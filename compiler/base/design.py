import math
import copy
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
        ok_list = ['ms_flop',
                   'ms_flop_horz_pitch',
                   'bitcell',
                   'body_tap',
                   'cam_bitcell',
                   'contact',
                   'ptx',
                   'pinv',
                   'ptx_spice',
                   'SignalGate',
                   'sram',
                   'hierarchical_predecode2x4',
                   'hierarchical_predecode3x8']
        if name not in design.name_map:
            design.name_map.append(name)
        elif self.__class__.__name__ in ok_list:
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
        self.poly_to_field_poly = drc["poly_to_field_poly"]
        self.contact_to_gate = drc["contact_to_gate"]
        self.well_enclose_active = drc["well_enclosure_active"]
        self.implant_enclose_active = drc["implant_enclosure_active"]
        self.implant_space = drc["implant_to_implant"]

        self.minarea_metal1_contact = drc["minarea_metal1_contact"]

        self.wide_m1_space = drc["metal1_to_metal1_wide"]
        self.line_end_space = drc["metal1_to_metal1_line_end"]
        self.parallel_line_space = drc["parallel_metal1_to_metal1"]
        self.metal1_minwidth_fill = utils.ceil(drc["minarea_metal1_minwidth"]/self.m1_width)
        self.poly_vert_space = drc["poly_end_to_end"]
        self.parallel_via_space = drc["parallel_via_space"]
        self.metal1_min_enclosed_area = drc["metal1_min_enclosed_area"]

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

    def get_layer_shapes(self, layer, purpose="drawing"):
        filter_match = lambda x: (
                    x.__class__.__name__ == "rectangle" and x.layerNumber == tech_layers[layer] and
                    x.layerPurpose == tech_purpose[purpose])
        return filter(filter_match, self.objs)

    def get_gds_layer_shapes(self, cell, layer, purpose="drawing"):
        return cell.gds.getShapesInLayer(tech_layers[layer], tech_purpose[purpose])

    def get_poly_fills(self, cell):
        poly_dummies = self.get_gds_layer_shapes(cell, "po_dummy", "po_dummy")
        poly_rects = self.get_gds_layer_shapes(cell, "poly")

        # only polys with active layer interaction need to be filled
        polys = []
        actives = self.get_gds_layer_shapes(cell, "active")
        for poly_rect in poly_rects:
            for active in actives:
                if (poly_rect[0][0] > active[0][0] and poly_rect[1][0] < active[1][0]  # contained in x_direction
                        and poly_rect[0][1] < active[0][1] and poly_rect[1][1] > active[1][1]):
                    polys.append(poly_rect)
        if len(polys) == 0 and len(poly_dummies) == 2: # this may be a composite cell. In which case dummy polys should be added to guide
            result = {}
            left = copy.deepcopy(min(poly_dummies, key=lambda rect: rect[0][0]))
            left[0][0] -= self.poly_pitch
            left[1][0] -= self.poly_pitch
            result["left"] = [left]
            right = copy.deepcopy(max(poly_dummies, key=lambda rect: rect[0][0]))
            right[0][0] += self.poly_pitch
            right[1][0] += self.poly_pitch
            result["right"] = [right]
            return result




        fills = []
        for poly_rect in polys:
            x_offset = poly_rect[0][0]
            potential_fills = [-2, 2]  # need -2 and +2 poly pitches from current x offset filled
            mid_point = 0.5 * (poly_rect[0][1] + poly_rect[1][1]) # y midpoint
            for candidate in polys + poly_dummies:
                if not candidate[0][1] < mid_point < candidate[1][1]:  # not on the same row
                    continue
                integer_space = int(round((candidate[0][0] - x_offset)/self.poly_pitch)) # space away from current poly
                if integer_space in potential_fills:
                    potential_fills.remove(integer_space)
            for potential_fill in potential_fills:  # fill unfilled spaces
                fill_copy = copy.deepcopy(poly_rect)
                x_space = potential_fill * self.poly_pitch
                fill_copy[0][0] += x_space
                fill_copy[1][0] += x_space
                fills.append(fill_copy)
        # make the fills unique by x_offset by combining fills with the same x offset
        fills = list(sorted(fills, key=lambda x: x[0][0]))
        merged_fills = {"left": [], "right": []}

        def add_to_merged(fill):
            if fill[0][0] < 0.5*cell.width:
                merged_fills["left"].append(fill)
            else:
                merged_fills["right"].append(fill)
        if len(fills) > 0:
            current_fill = copy.deepcopy(fills[0])
            x_offset = utils.ceil(current_fill[0][0])
            for fill in fills:
                if utils.ceil(fill[0][0]) == x_offset:
                    current_fill[0][1] = min(fill[0][1], current_fill[0][1])
                    current_fill[1][1] = max(fill[1][1], current_fill[1][1])
                else:
                    add_to_merged(current_fill)
                    current_fill = fill
                    x_offset = utils.ceil(current_fill[0][0])
            add_to_merged(current_fill)
        return merged_fills



    def get_dummy_poly(self, cell, from_gds=True):
        if "po_dummy" in tech_layers:
            if from_gds:
                rects = cell.gds.getShapesInLayer(tech_layers["po_dummy"], tech_purpose["po_dummy"])
            else:
                shapes = self.get_layer_shapes("po_dummy", "po_dummy")
                rects = map(lambda x: x.boundary, shapes)

            leftmost = min(map(lambda x: x[0], map(lambda x: x[0], rects)))
            rightmost = max(map(lambda x: x[0], map(lambda x: x[1], rects)))
            return (leftmost, rightmost)

    def add_dummy_poly(self, cell, instances, words_per_row, from_gds=True):
        cell_fills = self.get_poly_fills(cell)

        def add_fill(x_offset, direction="left"):
            for rect in cell_fills[direction]:
                self.add_rect("po_dummy", offset=vector(x_offset + rect[0][0], rect[0][1]),
                              width=self.poly_width, height=rect[1][1] - rect[0][1])

        if len(cell_fills.values()) > 0:
            if words_per_row > 1:
                for inst in instances:
                    add_fill(inst.lx(), "left")
                    add_fill(inst.lx(), "right")
            else:
                add_fill(instances[0].lx(), "left")
                add_fill(instances[-1].lx(), "right")
            if hasattr(self, "tap_offsets") and len(self.tap_offsets) > 0:
                tap_width = utils.get_body_tap_width()
                tap_offsets = self.tap_offsets
                for offset in tap_offsets:
                    if offset > tap_width:
                        add_fill(offset - instances[-1].width, "right")
                        add_fill(offset + tap_width, "left")

    def fill_array_layer(self, layer, cell, module_insts=[]):
        if not (hasattr(self, "tap_offsets") and len(self.tap_offsets) > 0):
            return

        if layer in tech_purpose:
            purpose = tech_purpose[layer]
        else:
            purpose = tech_purpose["drawing"]
        rects = cell.gds.getShapesInLayer(tech_layers[layer], purpose=purpose)
        tap_offsets = self.tap_offsets[1:] # first tap offset doesn't have to be filled
        tap_width = utils.get_body_tap_width()

        for rect in rects:
            (ll, ur) = rect
            # only right hand side  needs to be extended
            if ur[0] >= cell.width:
                right_extension = ur[0] - cell.width
                for tap_offset in tap_offsets:
                    self.add_rect(layer, offset=vector(tap_offset, ll[1]), height=ur[1] - ll[1],
                                  width=tap_width + right_extension)
                for i in range(1, len(module_insts)):
                    current_inst = module_insts[i]
                    prev_inst = module_insts[i-1]
                    if current_inst.lx() == prev_inst.rx():
                        continue
                    self.add_rect(layer, offset=vector(prev_inst.rx() + right_extension, ll[1]), height=ur[1] - ll[1],
                                  width=current_inst.lx() - prev_inst.rx())







        

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
