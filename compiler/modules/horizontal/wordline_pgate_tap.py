import tech
from base import utils, contact
from base.contact import m1m2, cross_m1m2
from base.design import design, NIMP, PIMP, ACTIVE, METAL1, NWELL, PWELL, METAL2
from base.hierarchy_layout import GDS_ROT_270
from base.unique_meta import Unique
from base.vector import vector
from globals import OPTS
from modules.horizontal.wordline_pgate_horizontal import wordline_pgate_horizontal
from tech import drc


class wordline_pgate_tap(design, metaclass=Unique):
    rotation_for_drc = GDS_ROT_270

    @classmethod
    def get_name(cls, pgate_mod, implant_type):
        return "{}_{}_tap".format(pgate_mod.name, implant_type[0])

    def __init__(self, pgate_mod: wordline_pgate_horizontal, implant_type):
        super().__init__(self.name)
        self.pgate_mod = pgate_mod
        self.implant_type = implant_type
        self.create_layout()
        if hasattr(tech, "add_tech_layers"):
            tech.add_tech_layers(self)

    def create_layout(self):
        bitcell_tap = self.create_mod_from_str(OPTS.body_tap)
        self.width = self.pgate_mod.width
        self.height = bitcell_tap.height

        reference_mod = self.pgate_mod

        pgate_layer = PIMP if self.implant_type == NIMP else NIMP
        pgate_rect = reference_mod.get_layer_shapes(pgate_layer)[0]

        implant_bottom = pgate_rect.uy() - reference_mod.height
        implant_top = self.height + pgate_rect.by()

        active_bottom = implant_bottom + self.implant_enclose_active
        active_top = implant_top - self.implant_enclose_active

        # active
        if self.pgate_mod.insert_poly_dummies:
            bottom_offsets, top_offsets = reference_mod.get_dummy_y_offsets(reference_mod)

            top_offsets = [x - reference_mod.height for x in top_offsets]
            dummy_bottom = max(top_offsets) + reference_mod.poly_width

            dummy_top = self.height + min(bottom_offsets)
            active_space = drc["poly_dummy_to_active"]
            active_top = min(active_top, dummy_top - active_space)
            active_bottom = max(active_bottom, dummy_bottom + active_space)

        active_height = max(contact.well.first_layer_width,
                            active_top - active_bottom)

        min_active_area = drc.get("minarea_cont_active_thin", self.get_min_area(ACTIVE))
        active_width = max(contact.well.first_layer_width,
                           utils.ceil(min_active_area / active_height))

        mid_y = 0.5 * (implant_top + implant_bottom)

        implant_height = implant_top - implant_bottom
        implant_width = utils.ceil(drc.get("minarea_implant", 0) / implant_height)
        implant_width = max(self.implant_width, active_width + 2 * self.implant_enclose_active,
                            implant_width)

        self.width = implant_width
        mid_x = 0.5 * self.width

        num_contacts = self.calculate_num_contacts(max(active_width, active_height))
        # add contacts
        if active_width > active_height:
            rotate = 90
        else:
            rotate = 0

        self.add_contact_center(contact.well.layer_stack, offset=vector(mid_x, mid_y),
                                size=[1, num_contacts], rotate=rotate)
        # implant
        self.add_rect_center(self.implant_type, vector(mid_x, mid_y), width=implant_width,
                             height=implant_top - implant_bottom)
        # add active
        self.add_rect_center(ACTIVE, offset=vector(mid_x, mid_y),
                             width=active_width, height=active_height)
        self.add_boundary()

    @staticmethod
    def add_buffer_taps(design_self: design, x_offset, y_offset,
                        module_insts, pwell_tap, nwell_tap):
        tap_insts = []
        layers = [PWELL, NWELL]
        for buffer_index, buffer_inst in enumerate(module_insts):
            mod = buffer_inst.mod
            # add wells
            for layer in layers:
                mod_rects = mod.get_layer_shapes(layer)
                for rect in mod_rects:
                    rect_x = x_offset + buffer_inst.lx() + rect.lx()
                    rect_y = y_offset
                    design_self.add_rect(layer, offset=vector(rect_x, rect_y),
                                         width=rect.width, height=pwell_tap.height)

            # join the power pins
            power_m2_rects = []
            for rect in mod.get_layer_shapes(ACTIVE):
                m2_rect = design_self. \
                    add_rect_center(METAL2,
                                    offset=vector(x_offset + buffer_inst.lx() + rect.cx(),
                                                  y_offset + 0.5 * nwell_tap.height),
                                    width=m1m2.height, height=nwell_tap.height)
                power_m2_rects.append(m2_rect)

            left_m2, right_m2 = sorted(power_m2_rects, key=lambda x: x.lx())

            taps = [pwell_tap, nwell_tap]
            if mod.mirror:
                taps = list(reversed(taps))
            left_tap, right_tap = taps
            left_x = -0.5 * left_tap.width
            right_x = mod.width - 0.5 * right_tap.width

            if buffer_index == 0:
                left_x = 0
            if buffer_index == len(module_insts) - 1:
                right_x = mod.width - right_tap.width

            left_x += buffer_inst.lx()
            right_x += buffer_inst.lx()
            for tap_x, tap, m2_rect in [(left_x, left_tap, left_m2),
                               (right_x, right_tap, right_m2)]:
                tap_inst = design_self.add_inst(tap.name, tap,
                                                offset=vector(tap_x, y_offset))
                design_self.connect_inst([])
                tap_insts.append(tap_inst)
                # connect to power
                design_self.add_rect(METAL1,
                                     offset=vector(m2_rect.cx(),
                                                   tap_inst.cy() - 0.5 * design_self.m1_width),
                                     width=tap_inst.cx() - m2_rect.cx())
                design_self.add_cross_contact_center(cross_m1m2, vector(m2_rect.cx(),
                                                                        tap_inst.cy()),
                                                     rotate=True)
        return tap_insts
