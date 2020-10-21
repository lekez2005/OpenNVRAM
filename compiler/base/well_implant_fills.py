from base import utils
from base.design import design, NWELL, NIMP, PIMP
import tech


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
                rect_top = overlap_rect.uy()
                rect_bottom = max(overlap_rect.by(), left_mod_rect.by())
            else:
                rect_bottom = overlap_rect.by()
                rect_top = min(overlap_rect.uy(), left_mod_rect.uy())

            fill_rect = (layer, rect_bottom, rect_top, left_mod_rect, overlap_rect)
            all_fills.append(fill_rect)
    return all_fills
