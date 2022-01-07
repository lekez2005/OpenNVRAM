import debug
from base import contact
from base.design import design, POLY, ACTIVE
from base.flatten_layout import flatten_rects
from base.vector import vector
from tech import drc


def get_vias(obj: design):
    return [x for x in enumerate(obj.insts) if isinstance(x[1].mod, contact.contact)]


def add_stdc(obj: design):
    """Add stdc around active rects"""
    active_rects = obj.get_layer_shapes(ACTIVE)
    for rect in active_rects:
        obj.add_rect("stdc", rect.ll(), width=rect.width, height=rect.height)


def seal_poly_vias(obj: design):
    """Add npc around poly contacts"""
    poly_via_insts = [x[1] for x in get_vias(obj) if x[1].mod.layer_stack[0] == POLY]
    if not poly_via_insts:
        return
    debug.info(2, f"Sealing Poly vias in module {obj.name}")

    sample_via = poly_via_insts[0].mod
    x_extension = 0.5 * (sample_via.first_layer_width - sample_via.width)
    y_extension = 0.5 * (sample_via.first_layer_height - sample_via.height)

    npc_enclose_poly = drc.get("npc_enclose_poly")

    poly_via_insts = list(sorted(poly_via_insts, key=lambda x: (x.lx(), x.by())))

    # group vias that are close together

    contact_span = 0.5  # max x/y space between contacts for them to be grouped together
    via_groups = []
    for via_inst in poly_via_insts:
        found = False
        for via_group in via_groups:
            (left_x, right_x, bot, top, existing_insts) = via_group
            span_left = left_x - contact_span
            span_right = right_x + contact_span
            span_top = top + contact_span
            span_bot = bot - contact_span

            if span_left <= via_inst.cx() <= span_right:
                if span_bot <= via_inst.cy() <= span_top:
                    existing_insts.append(via_inst)
                    via_group[0] = min(left_x, via_inst.lx())
                    via_group[1] = max(right_x, via_inst.rx())
                    via_group[2] = min(bot, via_inst.by())
                    via_group[3] = max(top, via_inst.uy())
                    found = True
                    break

        if not found:
            via_groups.append([via_inst.lx(), via_inst.rx(),
                               via_inst.by(), via_inst.uy(),
                               [via_inst]])

    for left, right, bot, top, _ in via_groups:
        x_offset = left - npc_enclose_poly - x_extension
        width = right + npc_enclose_poly + x_extension - x_offset
        y_offset = bot - npc_enclose_poly - y_extension
        height = top + npc_enclose_poly + y_extension - y_offset
        obj.add_rect("npc", vector(x_offset, y_offset), width=width, height=height)


def flatten_vias(obj: design):
    """Flatten vias by moving via shapes from via instance to top level
       Also combine multiple rects into encompassing rect
    """
    debug.info(2, f"Flattening vias in module {obj.name}")
    all_via_inst = get_vias(obj)
    all_via_index = [x[0] for x in all_via_inst]
    insts = [x[1] for x in all_via_inst]
    flatten_rects(obj, insts, all_via_index)


def enhance_module(obj: design):
    if getattr(obj, "sky_130_enhanced", False):
        return
    debug.info(2, f"Enhancing module {obj.name}")
    obj.sky_130_enhanced = True
    # add stdc and seal poly before flattening vias
    add_stdc(obj)
    seal_poly_vias(obj)
    flatten_vias(obj)
