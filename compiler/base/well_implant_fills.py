from base import utils
from base.design import design, NWELL, NIMP, PIMP, METAL1, PO_DUMMY, POLY, DRAWING
import tech
from base import contact
from base.geometry import instance
from base.hierarchy_layout import GDS_ROT_270, GDS_ROT_90
from base.rotation_wrapper import RotationWrapper
from base.vector import vector

TOP = "top"
BOTTOM = "bottom"
VERTICAL = "vertical"
HORIZONTAL = "horizontal"


def calculate_tx_metal_fill(tx_width, design_mod: design):
    """Calculate metal fill properties
    if tx is wide enough to not need to be filled, just return None
    design_mod acts as gateway to design class parameters
    """
    num_contacts = design_mod.calculate_num_contacts(tx_width)
    test_contact = contact.contact(contact.well.layer_stack,
                                   dimensions=[1, num_contacts])
    if test_contact.second_layer_height > design_mod.metal1_minwidth_fill:
        return None
    fill_width = utils.round_to_grid(2 * (design_mod.poly_pitch - 0.5 * design_mod.m1_width
                                          - design_mod.m1_space))

    m1_space = design_mod.get_space_by_width_and_length(METAL1, max_width=fill_width,
                                                        min_width=design_mod.m1_width,
                                                        run_length=tx_width)
    # actual fill width estimate based on space
    fill_width = utils.round_to_grid(2 * (design_mod.poly_pitch
                                          - 0.5 * design_mod.m1_width - m1_space))

    fill_height = utils.ceil(max(design_mod.minarea_metal1_contact / fill_width,
                                 test_contact.first_layer_height))
    fill_width = utils.ceil(max(design_mod.m1_width,
                                design_mod.minarea_metal1_contact / fill_height))
    y_offset = 0.5 * tx_width - 0.5 * test_contact.first_layer_height
    fill_top = y_offset + fill_height
    return y_offset, fill_top, fill_width, fill_height


def get_default_fill_layers():
    """Get layers that result in min spacing issues when two modules are placed side by side"""
    if hasattr(tech, "default_fill_layers"):
        layers = tech.default_fill_layers
    else:
        layers = [NWELL, NIMP, PIMP]
    if hasattr(tech, "default_fill_purposes"):
        purposes = tech.default_fill_purposes
    else:
        purposes = ["drawing", "drawing", "drawing"]
    assert len(layers) == len(purposes), "Number of layers and purposes specified not equal"
    return layers, purposes


def create_wells_and_implants_fills(left_mod: design, right_mod: design,
                                    layers=None, purposes=None):
    """
    Create all rects needed to fill between two adjacent modules to prevent minimum DRC spacing rules
    :param left_mod: The module on the left
    :param right_mod: The module on the right
    :param layers: The layers to be filled. Leave empty to use specifications from technology file
    :param purposes: The purposes of the layers to be filled. Can also leave empty
    :return: Fill list of rects tuples of (rect_layer, rect_bottom, rect_top,
                                           reference_rect_on_left, reference_rect_on_right)
    """
    default_layers, default_purposes = get_default_fill_layers()
    if layers is not None and purposes is None:
        purposes = [DRAWING] * len(layers)
    if layers is None:
        layers = default_layers
    if purposes is None:
        purposes = default_purposes

    all_fills = []

    for i in range(len(layers)):
        layer = layers[i]
        purpose = purposes[i]

        left_mod_rects = left_mod.get_layer_shapes(layer, purpose=purpose)
        right_mod_rects = right_mod.get_layer_shapes(layer, purpose=purpose)

        for left_mod_rect in left_mod_rects:
            # find right mod rect which overlaps
            overlap_rect = None
            for right_mod_rect in right_mod_rects:
                if left_mod_rect.by() < right_mod_rect.by():
                    lowest_rect, highest_rect = left_mod_rect, right_mod_rect
                else:
                    lowest_rect, highest_rect = right_mod_rect, left_mod_rect
                if lowest_rect.uy() > highest_rect.by():
                    overlap_rect = right_mod_rect
                    break
            if overlap_rect is None:
                continue
            # find alignment point. e.g. if alignment is on top, then keep the tops aligned
            if utils.ceil(overlap_rect.uy()) == utils.ceil(left_mod_rect.uy()):
                rect_top = min(overlap_rect.uy(), left_mod_rect.uy())
                rect_bottom = max(overlap_rect.by(), left_mod_rect.by())
            else:
                rect_bottom = max(overlap_rect.by(), left_mod_rect.by())
                rect_top = min(overlap_rect.uy(), left_mod_rect.uy())

            fill_rect = (layer, rect_bottom, rect_top, left_mod_rect, overlap_rect)
            all_fills.append(fill_rect)
    return all_fills


def well_implant_instance_fills(source_inst: instance, target_inst: instance,
                                direction=VERTICAL,
                                layers=None, purposes=None):
    default_layers, default_purposes = get_default_fill_layers()
    is_vertical = direction == VERTICAL

    if layers is None:
        layers = default_layers
    if purposes is None:
        purposes = default_purposes

    def source_func(x):
        return x.uy() if is_vertical else x.rx()

    def target_func(x):
        return x.by() if is_vertical else x.lx()

    def is_edge_rect(rect, inst, prop_scale):
        """Considered edge rect if it's extremity is within the layer space"""
        layer_space = source_inst.mod.get_space(layer)

        if prop_scale == 1:
            if is_vertical:
                return rect.uy() + layer_space > inst.height
            else:
                return rect.rx() + layer_space > inst.width
        else:
            if is_vertical:
                return rect.by() - layer_space < 0
            else:
                return rect.lx() - layer_space < 0

    def get_extremity_rects(inst, property_func, prop_scale):
        """prop_scale = 1 for max comparison and -1 for min comparison"""
        rects = inst.get_layer_shapes(layer, purpose=purpose, recursive=True)
        if not rects:
            return []
        max_val = max([prop_scale * x for x in map(utils.floor, map(property_func, rects))])
        extremity_rects = [x for x in rects if prop_scale * utils.floor(property_func(x)) >= max_val]
        return [x for x in extremity_rects if is_edge_rect(x, inst, prop_scale)]

    results = []

    for i in range(len(layers)):
        layer = layers[i]
        purpose = purposes[i]
        min_width = source_inst.mod.get_min_layer_width(layer)
        source_rects = get_extremity_rects(source_inst, source_func, 1)
        target_rects = get_extremity_rects(target_inst, target_func, -1)
        for source_rect in source_rects:
            for target_rect in target_rects:
                if is_vertical:
                    start = max(source_rect.lx(), target_rect.lx())
                    end = min(source_rect.rx(), target_rect.rx())
                    width = end - start
                    x_offset = start
                    y_offset = source_rect.uy()
                    height = (source_inst.height - y_offset) + target_rect.by()
                else:
                    start = max(source_rect.by(), target_rect.by())
                    end = min(source_rect.uy(), target_rect.uy())
                    x_offset = source_rect.rx()
                    y_offset = start
                    width = (source_inst.width - x_offset) + target_rect.lx()
                    height = end - start
                if end - start > min_width:
                    results.append((layer, x_offset, y_offset, width, height))
    return results


def fill_horizontal_poly(self: design, reference_inst: instance, direction=TOP):
    """
    Fill dummy poly for instances which have been rotated by 90 or 270
    :param self: The parent module where the fills are inserted
    :param reference_inst: The instance around which the fills will be inserted
    :param direction: Whether to insert above or below. Options: top, bottom
    :return:
    """
    if isinstance(reference_inst.mod, RotationWrapper):
        original_vertical_mod = reference_inst.mod.child_mod
        rotation = reference_inst.mod.child_inst.rotate
    else:
        original_vertical_mod = reference_inst.mod
        rotation = reference_inst.rotate

    dummy_fills = self.get_poly_fills(original_vertical_mod)

    if not dummy_fills:
        return

    if ((direction == TOP and rotation == GDS_ROT_90)
            or direction == BOTTOM and rotation == GDS_ROT_270):
        key = "right"
    else:
        key = "left"

    real_poly = original_vertical_mod.get_layer_shapes(POLY)
    max_width = max(real_poly, key=lambda x: x.width).width

    for rect in dummy_fills[key]:
        fill_x = 0.5 * self.poly_to_field_poly
        fill_width = reference_inst.width - 2 * fill_x
        ll, ur = map(vector, rect)
        if direction == TOP:
            if key == "left":
                y_shift = original_vertical_mod.width - ur[0]
            else:
                y_shift = ll[0]
            y_shift += 2 * (max_width - self.poly_width)
        else:
            if key == "left":
                y_shift = ll[0]
            else:
                y_shift = original_vertical_mod.width - ur[0]
            y_shift -= (max_width - self.poly_width)

        y_offset = reference_inst.by() + y_shift
        x_offset = reference_inst.lx() + fill_x
        self.add_rect(PO_DUMMY, offset=vector(x_offset, y_offset),
                      width=fill_width, height=self.poly_width)
