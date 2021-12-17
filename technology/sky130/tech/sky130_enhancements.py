import debug
from base import contact
from base.design import design, POLY, ACTIVE
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

    for via_inst in poly_via_insts:
        x_offset = via_inst.lx() - npc_enclose_poly - x_extension
        width = via_inst.rx() + npc_enclose_poly + x_extension - x_offset
        y_offset = via_inst.by() - npc_enclose_poly - y_extension
        height = via_inst.uy() + npc_enclose_poly + y_extension - y_offset
        obj.add_rect("npc", vector(x_offset, y_offset), width=width, height=height)


def flatten_vias(obj: design):
    """Flatten vias by moving via shapes from via instance to top level
       Also combine multiple rects into encompassing rect
    """
    debug.info(2, f"Flattening vias in module {obj.name}")
    all_via_inst = get_vias(obj)
    for _, via_inst in all_via_inst:
        for layer in via_inst.mod.layer_stack:
            layer_rects = via_inst.get_layer_shapes(layer, recursive=False)

            x_sort = list(sorted(layer_rects, key=lambda x: x.lx()))
            y_sort = list(sorted(layer_rects, key=lambda x: x.by()))

            ll = vector(x_sort[0].lx(), y_sort[0].by())
            ur = vector(x_sort[-1].rx(), y_sort[-1].uy())
            obj.add_rect(layer, ll, width=ur.x - ll.x, height=ur.y - ll.y)

    all_via_index = [x[0] for x in all_via_inst]
    obj.insts = [inst for inst_index, inst in enumerate(obj.insts)
                 if inst_index not in all_via_index]
    obj.conns = [conn for conn_index, conn in enumerate(obj.conns)
                 if conn_index not in all_via_index]


def enhance_module(obj: design):
    debug.info(1, f"Enhancing module {obj.name}")
    # add stdc and seal poly before flattening vias
    add_stdc(obj)
    seal_poly_vias(obj)
    flatten_vias(obj)
