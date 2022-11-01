# find open space in a module given the layer
from base.geometry import rectangle
from base.utils import round_to_grid
from base.design import design
from base.vector import vector

HORIZONTAL = "horizontal"
VERTICAL = "vertical"


def get_extremities(obj, direction=None):
    if direction == HORIZONTAL:
        extremities = [obj.lx(), obj.rx()]
    else:
        extremities = [obj.by(), obj.uy()]
    return round_to_grid(extremities[0]), round_to_grid(extremities[1])


def get_range_overlap(range_1, range_2):
    range_1 = list(sorted(range_1))
    range_2 = list(sorted(range_2))
    range_1, range_2 = sorted((range_1, range_2), key=lambda x: x[1] - x[0])
    return (range_2[0] <= range_1[0] <= range_2[1] or
            range_2[0] <= range_1[1] <= range_2[1])


def validate_clearances(clearances):
    results = []
    for clearance in clearances:
        if clearance[1] > clearance[0]:
            results.append(clearance)
    return results


def find_clearances(module: design, layer, direction=HORIZONTAL, existing=None, region=None,
                    recursive=True, recursive_insts=None):
    if existing is None:
        edge = module.width if direction == HORIZONTAL else module.height
        existing = [(0, round_to_grid(edge))]
        full_range = existing[0]
    else:
        full_range = (min(map(min, existing)), max(map(max, existing)))
    if region is None:
        edge = module.width if direction == VERTICAL else module.height
        region = (0, round_to_grid(edge))

    rects = module.get_layer_shapes(layer, recursive=recursive)
    if recursive_insts:
        for inst in recursive_insts:
            rects.extend(inst.get_layer_shapes(layer, recursive=True))
    for rect in rects:
        # ensure rect is within considered range
        region_edges = get_extremities(rect, HORIZONTAL if direction == VERTICAL else VERTICAL)
        if not get_range_overlap(region_edges, region):
            continue

        edges = get_extremities(rect, direction)
        if not get_range_overlap(full_range, edges):
            continue

        new_clearances = []
        for clearance in existing:
            if get_range_overlap(clearance, edges):
                if clearance[0] <= edges[0]:
                    new_clearances.extend([(clearance[0], edges[0]), (edges[1], clearance[1])])
                else:
                    new_clearances.append((edges[1], clearance[1]))
            else:
                new_clearances.append(clearance)
        existing = validate_clearances(new_clearances)

    return existing


def combine_rects(rect_1, rect_2):
    x_offset = min(rect_1.lx(), rect_2.lx())
    y_offset = min(rect_1.by(), rect_2.by())
    width = max(rect_1.rx(), rect_2.rx()) - x_offset
    height = max(rect_1.uy(), rect_2.uy()) - y_offset
    combined_rect = rectangle(layerNumber=rect_1.layerNumber,
                              layerPurpose=rect_1.layerPurpose,
                              offset=vector(x_offset, y_offset),
                              width=width, height=height)
    return combined_rect


def extract_unique_rects(rects, min_space=0):
    unique_rects = []
    for original_rect in rects:
        overlap = False
        expanded_rect = rectangle(layerNumber=0,
                                  offset=original_rect.ll() - vector(min_space, min_space),
                                  width=original_rect.width + 2 * min_space,
                                  height=original_rect.height + 2 * min_space)

        for existing_index, existing_rect in enumerate(unique_rects):
            if expanded_rect.overlaps(existing_rect):
                combined_rect = combine_rects(original_rect, existing_rect)
                unique_rects[existing_index] = combined_rect
                overlap = True
                break
        if not overlap:
            unique_rects.append(original_rect)

    return unique_rects
