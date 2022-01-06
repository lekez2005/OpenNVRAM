from typing import List

from base.design import design
from base.geometry import geometry, rectangle
from base.pin_layout import pin_layout


class EmptyMod(design):
    pass


empty_mod = EmptyMod("dummy")


def flatten_rects(self: design, insts: List[geometry] = None,
                  inst_indices: List[int] = None):
    """Move rects in insts to top-level 'self' """
    if insts is None:
        inst_indices, insts = enumerate(self.insts)
    if inst_indices is None:
        inst_indices = list(range(len(insts)))

    flat_rects = self.get_layer_shapes(layer=None, recursive=True, insts=insts)
    other_obj = [x for x in self.objs if not isinstance(x, rectangle)]

    # turn pins to rects
    pin_indices = []
    for shape_index, shape in enumerate(flat_rects):
        if isinstance(shape, pin_layout):
            self.add_rect(shape.layer, shape.ll(), width=shape.width(),
                          height=shape.height())
            pin_indices.append(shape_index)
    flat_rects = [rect for pin_index, rect in enumerate(flat_rects) if pin_index not in pin_indices]

    self.objs = other_obj + flat_rects

    empty_conn_indices = []
    # remove inst if no spice connection
    for inst_index, inst in zip(inst_indices, insts):
        if self.conns[inst_index]:
            inst.mod = empty_mod
        else:
            empty_conn_indices.append(inst_index)

    self.insts = [inst for inst_index, inst in enumerate(self.insts)
                  if inst_index not in empty_conn_indices]
    self.conns = [conn for conn_index, conn in enumerate(self.conns)
                  if conn_index not in empty_conn_indices]
